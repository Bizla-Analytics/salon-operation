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
  *pg_dump*) printf 'PGDMP synthetic archive\n' ;;
  *'pg_restore --list'*) cat > /dev/null ;;
  *' ps -q web '*) ;;
  *' backup '*) [[ "${FAIL_UPLOAD:-0}" != 1 ]] || exit 7 ;;
  *' run -d --name salonops-rehearsal-'*) echo synthetic-container ;;
esac
MOCK
chmod +x "$tmp/bin/docker"
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
echo 'Operational script safety/ordering tests: PASSED'
