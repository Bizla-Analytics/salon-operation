#!/usr/bin/env bash
# Invoke from a trusted, reviewed CI release. Defaults NEVER target the local DB.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ops_common.sh"
[[ $# == 7 ]] || die "Usage: ENV_FILE PROJECT COMPOSE_FILE BACKUP_ROOT RESTIC_ENV_FILE IMAGE EXPECTED_REGISTRY_PATH"
image=$6
expected_path=$7
[[ "$expected_path" =~ ^ghcr\.io/[a-z0-9_.-]+/[a-z0-9_.-]+$ ]] || die "Invalid expected registry path."
[[ "$image" == "$expected_path@sha256:"* ]] || die "Image repository does not match the approved repository."
digest=${image#"$expected_path@sha256:"}
[[ "$digest" =~ ^[a-f0-9]{64}$ ]] || die "Only immutable sha256 image digests can be deployed."
export SALONOPS_IMAGE="$image"
load_ops "${@:1:5}"
exec 8>"$BACKUP_ROOT/$PROJECT.deploy.lock"
flock -n 8 || die "Another deployment is running."
deploy_dc() {
    if [[ "${SALONOPS_USE_CADDY:-false}" == true ]]; then
        SALONOPS_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" -f "$(dirname "$COMPOSE_FILE")/compose.caddy.yaml" "$@"
    else dc "$@"; fi
}
deploy_dc pull web db
deploy_dc up -d --wait db
dc run --rm --no-deps web python manage.py check_database_security
# Backup MUST succeed off-server before applying any schema migration.
bash "$(dirname "${BASH_SOURCE[0]}")/backup.sh" "$ENV_FILE" "$PROJECT" "$COMPOSE_FILE" "$BACKUP_ROOT" "$RESTIC_ENV_FILE"
dc run --rm --no-deps web python manage.py migrate --noinput
deploy_dc up -d --wait --wait-timeout 120
dc exec -T web python manage.py migrate --check
dc exec -T web python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health/', timeout=5); assert r.status == 200"
printf '%s\n' "$image" > "$BACKUP_ROOT/$PROJECT.last-successful-image"
echo "Deployment passed. Old images and DB backups are retained; no automatic database rollback was performed."
