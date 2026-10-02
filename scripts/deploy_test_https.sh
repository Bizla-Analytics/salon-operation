#!/usr/bin/env bash
# DEV ONLY: HTTPS protections stay enabled; only backup destination is local.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/preview_common.sh"
[[ $# == 6 ]] || die "Usage: ENV_FILE salonops-dev COMPOSE_FILE BACKUP_ROOT IMAGE EXPECTED_REGISTRY_PATH"
image=$5
expected_path=$6
[[ "$expected_path" =~ ^ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+$ ]] || die "Invalid expected registry path."
[[ "$image" == "$expected_path@sha256:"* ]] || die "Unapproved image repository."
digest=${image#"$expected_path@sha256:"}
[[ "$digest" =~ ^[a-f0-9]{64}$ ]] || die "Only immutable sha256 image digests can be deployed."
export SALONOPS_IMAGE="$image"
[[ "$(basename "$3")" == compose.test.yaml ]] || die "Use standalone compose.test.yaml."
load_preview "${@:1:4}"
exec 8>"$BACKUP_ROOT/$PROJECT.deploy.lock"
flock -n 8 || die "Another test deployment is running."
dc pull web db proxy
dc up -d --wait db
dc run --rm --no-deps web python manage.py check_database_security
bash "$(dirname "${BASH_SOURCE[0]}")/backup_preview.sh" "$ENV_FILE" "$PROJECT" "$COMPOSE_FILE" "$BACKUP_ROOT"
dc stop web proxy
dc run --rm --no-deps web python manage.py migrate --noinput
dc up -d --wait --wait-timeout 120
dc exec -T web python manage.py check_production_security
dc exec -T web python manage.py migrate --check
dc exec -T web python -c "import urllib.request; assert urllib.request.urlopen('http://localhost:8000/health/', timeout=5).status == 200; r=urllib.request.urlopen(urllib.request.Request('http://localhost:8000/login/', headers={'X-Forwarded-Proto':'https'}), timeout=5); assert r.status == 200; assert 'Secure' in r.headers.get('Set-Cookie','')"
# Verify the ORIGIN certificate and login response, even if Cloudflare is enabled.
# Never use --insecure/-k. DNS/ports must permit the public CA to validate first.
ready=false
for attempt in $(seq 1 30); do
    if curl --fail --silent --show-error --max-time 10 \
        --resolve operations.shahinanalytics.com:443:127.0.0.1 \
        https://operations.shahinanalytics.com/login/ > /dev/null; then ready=true; break; fi
    sleep 5
done
[[ "$ready" == true ]] || die "Origin HTTPS not ready. Check DNS, ports 80/443 and Caddy logs; DB and backups were retained."
bash "$(dirname "${BASH_SOURCE[0]}")/backup_preview.sh" "$ENV_FILE" "$PROJECT" "$COMPOSE_FILE" "$BACKUP_ROOT"
printf '%s\n' "$image" > "$BACKUP_ROOT/$PROJECT.last-successful-image.partial"
mv "$BACKUP_ROOT/$PROJECT.last-successful-image.partial" "$BACKUP_ROOT/$PROJECT.last-successful-image"
echo "Test deployment passed: https://operations.shahinanalytics.com (local backups; not off-server protection)."
