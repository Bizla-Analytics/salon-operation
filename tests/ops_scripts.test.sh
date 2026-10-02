#!/usr/bin/env bash
# Offline command-contract tests. All dumps/credentials here are synthetic.
set -Eeuo pipefail
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/backups"
export OPS_LOG="$tmp/docker.log"
export PATH="$tmp/bin:$PATH"
touch "$OPS_LOG"
cat > "$tmp/bin/docker" <<'MOCK'
#!/usr/bin/env bash
set -eu
printf '%q ' "$@" >> "$OPS_LOG"; printf '\n' >> "$OPS_LOG"
case " $* " in
  *' config --format json '*) cat "$PREVIEW_CONFIG" ;;
  *pg_dump*) [[ "${FAIL_DUMP:-0}" != 1 ]] || exit 7; [[ "${EMPTY_DUMP:-0}" == 1 ]] || printf 'PGDMP synthetic archive\n' ;;
  *'pg_restore --list'*) [[ "${FAIL_ARCHIVE:-0}" != 1 ]] || exit 7; cat > /dev/null ;;
  *' ps -q web '*) ;;
  *' backup '*) [[ "${FAIL_UPLOAD:-0}" != 1 ]] || exit 7 ;;
  *' run -d --name salonops-rehearsal-'*) echo synthetic-container ;;
esac
MOCK
chmod +x "$tmp/bin/docker"
cat > "$tmp/bin/curl" <<'MOCK'
#!/usr/bin/env bash
printf 'curl %q ' "$@" >> "$OPS_LOG"; printf '\n' >> "$OPS_LOG"
[[ "${FAIL_TLS:-0}" != 1 ]]
MOCK
printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/bin/sleep"
chmod +x "$tmp/bin/curl" "$tmp/bin/sleep"
printf 'SALONOPS_IMAGE=synthetic:testing\n' > "$tmp/app.env"
printf 'RESTIC_REPOSITORY=s3:https://offsite.invalid/test\nRESTIC_PASSWORD=synthetic\n' > "$tmp/restic.env"
touch "$tmp/compose.yaml"
args=("$tmp/app.env" salonops-test "$tmp/compose.yaml" "$tmp/backups" "$tmp/restic.env")
for script in "$root"/scripts/*.sh; do bash -n "$script"; done

mkdir -p "$tmp/checkout/.git" "$tmp/checkout/backups"
if bash "$root/scripts/backup.sh" "$tmp/app.env" salonops-test "$tmp/compose.yaml" "$tmp/checkout/backups" "$tmp/restic.env" > /dev/null 2>&1; then
    echo 'Backup inside Git checkout accepted' >&2; exit 1
fi
[[ ! -s "$OPS_LOG" ]]

bash "$root/scripts/backup.sh" "${args[@]}" > /dev/null
grep -q 'forget.*salonops-test' "$OPS_LOG"
mapfile -t dumps < <(find "$tmp/backups" -name database.dump)
[[ ${#dumps[@]} == 1 ]]
[[ -f "$(dirname "${dumps[0]}")/uploaded" ]]
if [[ -n "$(find "$tmp/backups" -name '*.partial')" ]]; then echo 'Partial backup was not cleaned' >&2; exit 1; fi

: > "$OPS_LOG"
if FAIL_UPLOAD=1 bash "$root/scripts/backup.sh" "${args[@]}" > /dev/null 2>&1; then echo 'Failed upload accepted' >&2; exit 1; fi
if grep -q 'forget' "$OPS_LOG"; then echo 'Retention ran after failed upload' >&2; exit 1; fi

: > "$OPS_LOG"
bash "$root/scripts/restore_rehearsal.sh" "${dumps[0]}" > /dev/null
grep -q -- '--network none' "$OPS_LOG"
grep -q -- '--exit-on-error --no-owner --no-acl' "$OPS_LOG"
grep -q 'rm -f -v salonops-rehearsal-' "$OPS_LOG"
if grep -Eq 'type=bind|compose|--publish' "$OPS_LOG"; then echo 'Rehearsal accessed production mounts/network' >&2; exit 1; fi

: > "$OPS_LOG"
printf 'corrupted' >> "${dumps[0]}"
if bash "$root/scripts/restore_rehearsal.sh" "${dumps[0]}" > /dev/null 2>&1; then echo 'Checksum failure accepted' >&2; exit 1; fi
[[ ! -s "$OPS_LOG" ]]

image="ghcr.io/example/salonops@sha256:$(printf '%064d' 0)"
: > "$OPS_LOG"
if FAIL_UPLOAD=1 bash "$root/scripts/deploy.sh" "${args[@]}" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then echo 'Deployment accepted failed backup' >&2; exit 1; fi
if grep -q 'manage.py migrate' "$OPS_LOG"; then echo 'Migration ran before successful backup' >&2; exit 1; fi
for bad in synthetic:latest "ghcrXio/example/salonops@sha256:$(printf '%064d' 0)"; do
    : > "$OPS_LOG"
    if bash "$root/scripts/deploy.sh" "${args[@]}" "$bad" ghcr.io/example/salonops > /dev/null 2>&1; then echo 'Unapproved image accepted' >&2; exit 1; fi
    [[ ! -s "$OPS_LOG" ]]
done
# The optional preview path must never weaken production's Restic requirement.
python3 "$root/tests/preview_config_fixture.py" > "$tmp/preview.json"
export PREVIEW_CONFIG="$tmp/preview.json"
touch "$tmp/compose.preview.yaml"
chmod 600 "$tmp/app.env"
preview_args=("$tmp/app.env" salonops-dev "$tmp/compose.preview.yaml" "$tmp/preview-backups")
for flag in FAIL_DUMP EMPTY_DUMP FAIL_ARCHIVE; do
    : > "$OPS_LOG"
    if env "$flag=1" bash "$root/scripts/deploy_preview.sh" "${preview_args[@]}" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
        echo "Preview deployment accepted $flag" >&2; exit 1
    fi
    if grep -q 'manage.py migrate' "$OPS_LOG"; then echo 'Preview migrated before validated backup' >&2; exit 1; fi
done
: > "$OPS_LOG"
bash "$root/scripts/deploy_preview.sh" "${preview_args[@]}" "$image" ghcr.io/example/salonops > /dev/null
[[ $(grep -c pg_dump "$OPS_LOG") == 2 ]]
first_dump=$(grep -n pg_dump "$OPS_LOG" | head -n1 | cut -d: -f1)
migration=$(grep -n 'manage.py migrate --noinput' "$OPS_LOG" | cut -d: -f1)
[[ "$first_dump" -lt "$migration" ]]
[[ "$(cat "$tmp/preview-backups/salonops-dev.last-successful-image")" == "$image" ]]
if grep -Eq 'restic|offsite|down.*-v' "$OPS_LOG"; then echo 'Preview used offsite or destructive cleanup' >&2; exit 1; fi
bash "$root/scripts/backup_preview.sh" "${preview_args[@]}" > /dev/null
for project in salonops-prod main; do
    : > "$OPS_LOG"
    if bash "$root/scripts/deploy_preview.sh" "$tmp/app.env" "$project" "$tmp/compose.preview.yaml" "$tmp/preview-backups" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
        echo 'Preview accepted production project' >&2; exit 1
    fi
    [[ ! -s "$OPS_LOG" ]]
done
: > "$OPS_LOG"
if bash "$root/scripts/deploy_preview.sh" "${preview_args[@]}" synthetic:latest ghcr.io/example/salonops > /dev/null 2>&1; then
    echo 'Preview accepted mutable image' >&2; exit 1
fi
[[ ! -s "$OPS_LOG" ]]
chmod 644 "$tmp/app.env"
if bash "$root/scripts/deploy_preview.sh" "${preview_args[@]}" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
    echo 'Preview accepted publicly readable credentials' >&2; exit 1
fi
[[ ! -s "$OPS_LOG" ]]
chmod 600 "$tmp/app.env"
# Real config rejection happens before any pull, start, dump, or migration.
python3 -c 'import json,sys; p=sys.argv[1]; c=json.load(open(p)); c["services"]["web"]["ports"][0]["host_ip"]="0.0.0.0"; json.dump(c,open(p,"w"))' "$PREVIEW_CONFIG"
if bash "$root/scripts/deploy_preview.sh" "${preview_args[@]}" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
    echo 'Preview accepted public HTTP' >&2; exit 1
fi
[[ $(wc -l < "$OPS_LOG") == 1 ]]
grep -q 'config --format json' "$OPS_LOG"

# HTTPS-local also backs up before migration and never changes production mode.
python3 "$root/tests/preview_config_fixture.py" --https > "$PREVIEW_CONFIG"
touch "$tmp/compose.test.yaml"
https_args=("$tmp/app.env" salonops-dev "$tmp/compose.test.yaml" "$tmp/https-backups")
for flag in FAIL_DUMP EMPTY_DUMP FAIL_ARCHIVE; do
    : > "$OPS_LOG"
    if env "$flag=1" bash "$root/scripts/deploy_test_https.sh" "${https_args[@]}" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
        echo "HTTPS deployment accepted $flag" >&2; exit 1
    fi
    if grep -q 'manage.py migrate' "$OPS_LOG"; then echo 'HTTPS migrated before validated backup' >&2; exit 1; fi
done
: > "$OPS_LOG"
bash "$root/scripts/deploy_test_https.sh" "${https_args[@]}" "$image" ghcr.io/example/salonops > /dev/null
[[ $(grep -c pg_dump "$OPS_LOG") == 2 ]]
first_dump=$(grep -n pg_dump "$OPS_LOG" | head -n1 | cut -d: -f1)
migration=$(grep -n 'manage.py migrate --noinput' "$OPS_LOG" | cut -d: -f1)
[[ "$first_dump" -lt "$migration" ]]
grep -q 'check_production_security' "$OPS_LOG"
grep -q 'curl.*--resolve.*operations.shahinanalytics.com' "$OPS_LOG"
if grep -Eq -- '--insecure|restic|down.*-v' "$OPS_LOG"; then echo 'HTTPS safety contract failed' >&2; exit 1; fi
if FAIL_TLS=1 bash "$root/scripts/deploy_test_https.sh" "$tmp/app.env" salonops-dev "$tmp/compose.test.yaml" "$tmp/tls-failure-backups" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
    echo 'Invalid origin TLS was accepted' >&2; exit 1
fi
[[ ! -f "$tmp/tls-failure-backups/salonops-dev.last-successful-image" ]]
: > "$OPS_LOG"
if bash "$root/scripts/deploy_test_https.sh" "$tmp/app.env" salonops-prod "$tmp/compose.test.yaml" "$tmp/https-backups" "$image" ghcr.io/example/salonops > /dev/null 2>&1; then
    echo 'HTTPS-local accepted production project' >&2; exit 1
fi
[[ ! -s "$OPS_LOG" ]]
echo 'Operational script safety/ordering tests: PASSED'
