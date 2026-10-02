#!/usr/bin/env bash
# Local DEV backup only; no S3/Restic needed, no off-server protection claimed.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/preview_common.sh"
load_preview "$@"
exec 9>"$BACKUP_ROOT/$PROJECT.backup.lock"
flock -n 9 || die "A preview backup is already running."
stamp=$(date -u +%Y%m%dT%H%M%SZ)-$RANDOM
folder="$BACKUP_ROOT/$PROJECT/$stamp"
mkdir -p "$folder"
echo "Creating local-only PostgreSQL backup for $PROJECT..."
dc exec -T db sh -ec 'PGPASSWORD="$APP_DB_PASSWORD" pg_dump -h 127.0.0.1 -U "$APP_DB_USER" -d "$POSTGRES_DB" -Fc' > "$folder/database.dump.partial"
[[ -s "$folder/database.dump.partial" ]] || die "Empty preview dump; deployment must stop."
dc exec -T db pg_restore --list < "$folder/database.dump.partial" > /dev/null
mv "$folder/database.dump.partial" "$folder/database.dump"
(cd "$folder" && sha256sum database.dump > database.dump.sha256)
printf 'Project: %s\nCreated UTC: %s\nLOCAL ONLY: not protected against loss of this VPS.\n' "$PROJECT" "$stamp" > "$folder/release.txt"
web_id=$(dc ps -q web)
if [[ -n "$web_id" ]]; then docker inspect --format 'App image: {{.Config.Image}}' "$web_id" >> "$folder/release.txt"; fi
echo "Backup complete: $PROJECT/$stamp. All local backups are retained; monitor disk space."
