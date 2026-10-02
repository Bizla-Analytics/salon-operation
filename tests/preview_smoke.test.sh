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
cp "$root/compose.preview.yaml" "$tmp/"
cp "$root/deploy/postgres/10-create-app-user.sh" "$tmp/deploy/postgres/"
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
