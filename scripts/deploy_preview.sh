#!/usr/bin/env bash
# DEV ONLY. The production deploy.sh still requires a successful off-site backup.
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
load_preview "${@:1:4}"
exec 8>"$BACKUP_ROOT/$PROJECT.deploy.lock"
flock -n 8 || die "Another preview deployment is running."
dc pull web db
dc up -d --wait db
dc run --rm --no-deps web python manage.py check_database_security
# Fail closed: no migration if local dump or archive validation fails.
bash "$(dirname "${BASH_SOURCE[0]}")/backup_preview.sh" "$ENV_FILE" "$PROJECT" "$COMPOSE_FILE" "$BACKUP_ROOT"
# Avoid application writes while changing the schema. Failure leaves web stopped
# for investigation, never an automatic DB restore that could discard data.
dc stop web
dc run --rm --no-deps web python manage.py migrate --noinput
dc up -d --wait --wait-timeout 120
dc exec -T web python manage.py check
dc exec -T web python manage.py migrate --check
dc exec -T web python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health/', timeout=5); assert r.status == 200; r=urllib.request.urlopen('http://localhost:8000/login/', timeout=5); assert r.status == 200"
# On the first install the pre-migration archive has no application tables.
# Also take a post-migration backup suitable for an isolated restore rehearsal.
bash "$(dirname "${BASH_SOURCE[0]}")/backup_preview.sh" "$ENV_FILE" "$PROJECT" "$COMPOSE_FILE" "$BACKUP_ROOT"
printf '%s\n' "$image" > "$BACKUP_ROOT/$PROJECT.last-successful-image.partial"
mv "$BACKUP_ROOT/$PROJECT.last-successful-image.partial" "$BACKUP_ROOT/$PROJECT.last-successful-image"
echo "Private test deployment passed. Open it through an SSH tunnel, not the public Elastic IP."
