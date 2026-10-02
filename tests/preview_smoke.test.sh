#!/usr/bin/env bash
# Real PostgreSQL smoke/restore test ONLY on the disposable GitHub-hosted VM.
# Never run this on a VPS: it removes its own synthetic test volume afterward.
set -Eeuo pipefail
umask 077
[[ "${GITHUB_ACTIONS:-}" == true && "${RUNNER_ENVIRONMENT:-}" == github-hosted ]] || { echo 'Hosted CI only.' >&2; exit 1; }
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if docker volume inspect salonops-dev-pgdata > /dev/null 2>&1; then
    echo 'Existing preview volume found; refusing to touch it.' >&2; exit 1
fi
if [[ -n "$(docker ps -aq --filter label=com.docker.compose.project=salonops-dev)" ]]; then
    echo 'Existing preview project found; refusing to touch it.' >&2; exit 1
fi
tmp=$(mktemp -d)
mkdir -p "$tmp/deploy/postgres" "$tmp/scripts" "$tmp/backups"
cp "$root/compose.preview.yaml" "$root/compose.test.yaml" "$tmp/"
cp "$root/deploy/Caddyfile.test" "$tmp/deploy/"
chmod 644 "$tmp/deploy/Caddyfile.test"
cp "$root/deploy/postgres/10-create-app-user.sh" "$tmp/deploy/postgres/"
# Credentials stay private; this NON-secret script must be readable by Postgres.
chmod 644 "$tmp/deploy/postgres/10-create-app-user.sh"
cp "$root/scripts/"*.sh "$root/scripts/validate_preview.py" "$tmp/scripts/"
{
    echo "SECRET_KEY=$(openssl rand -hex 64)"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 32)"
    echo "POSTGRES_ADMIN_PASSWORD=$(openssl rand -hex 32)"
} > "$tmp/app.env"
export SALONOPS_IMAGE=salon-operation:local
source "$tmp/scripts/preview_common.sh"
load_preview "$tmp/app.env" salonops-dev "$tmp/compose.preview.yaml" "$tmp/backups"
cleanup() {
    dc down -v > /dev/null
    rm -rf -- "$tmp"
}
trap cleanup EXIT
dc up -d --wait db
dc run --rm --no-deps web python manage.py check_database_security
dc run --rm --no-deps web python manage.py migrate --noinput
dc up -d --wait --wait-timeout 120
dc exec -T web python manage.py check
dc exec -T web python manage.py migrate --check
dc exec -T web python -c "import urllib.request; assert urllib.request.urlopen('http://localhost:8000/health/').status == 200; r=urllib.request.urlopen('http://localhost:8000/login/'); assert r.status == 200; assert 'Secure' not in r.headers.get('Set-Cookie',''); print('Preview health/login: HTTP 200')"
dc exec -T web python -c "import os; assert 'POSTGRES_ADMIN_PASSWORD' not in os.environ; assert os.environ['DEBUG']=='False'; assert os.environ['APP_ENV']=='private-preview'"
dc exec -T web python manage.py shell -c "from operations.models import Branch; Branch.objects.create(code='CI_PREVIEW', name='CI preview synthetic branch')"
bash "$tmp/scripts/backup_preview.sh" "$tmp/app.env" salonops-dev "$tmp/compose.preview.yaml" "$tmp/backups"
mapfile -t dumps < <(find "$tmp/backups" -name database.dump)
[[ ${#dumps[@]} == 1 ]]
bash "$tmp/scripts/restore_rehearsal.sh" "${dumps[0]}"
echo 'Private preview real PostgreSQL smoke and isolated restore: PASSED'

# Switch the SAME test volume to HTTPS. Test Caddy with an isolated CI CA:
# never request a public certificate for the user's real domain from CI.
dc stop web
load_preview "$tmp/app.env" salonops-dev "$tmp/compose.test.yaml" "$tmp/backups"
dc run --rm --no-deps proxy caddy adapt --config /etc/caddy/Caddyfile --adapter caddyfile > /dev/null
sed -i '/^operations.shahinanalytics.com {/a\    tls internal' "$tmp/deploy/Caddyfile.test"
dc up -d --wait --wait-timeout 120
dc exec -T web python manage.py check_production_security
dc exec -T web python manage.py shell -c "from operations.models import Branch; assert Branch.objects.filter(code='CI_PREVIEW').exists(); print('HTTPS transition preserved test data')"
proxy_id=$(dc ps -q proxy)
ready=false
for attempt in $(seq 1 30); do
    if docker cp "$proxy_id:/data/caddy/pki/authorities/local/root.crt" "$tmp/root.crt" > /dev/null 2>&1; then ready=true; break; fi
    sleep 1
done
[[ "$ready" == true ]]
headers="$tmp/https.headers"
curl --fail --silent --show-error --retry 5 --retry-connrefused \
    --cacert "$tmp/root.crt" --resolve operations.shahinanalytics.com:443:127.0.0.1 \
    -D "$headers" https://operations.shahinanalytics.com/login/ > /dev/null
grep -qi 'set-cookie:.*Secure' "$headers"
grep -qi 'strict-transport-security: max-age=300' "$headers"
code=$(curl --silent --show-error --resolve operations.shahinanalytics.com:80:127.0.0.1 \
    -o /dev/null -w '%{http_code}' http://operations.shahinanalytics.com/login/)
[[ "$code" == 308 ]]
dc exec -T web python -c "import os; assert 'POSTGRES_ADMIN_PASSWORD' not in os.environ; assert os.environ['DEBUG']=='False'; assert os.environ['SESSION_COOKIE_SECURE']=='True'"
bash "$tmp/scripts/backup_preview.sh" "$tmp/app.env" salonops-dev "$tmp/compose.test.yaml" "$tmp/backups"
mapfile -t dumps < <(find "$tmp/backups" -name database.dump | sort)
[[ ${#dumps[@]} == 2 ]]
bash "$tmp/scripts/restore_rehearsal.sh" "${dumps[1]}"
echo 'Test HTTPS/Caddy, secure cookies, data preservation and local restore: PASSED'
