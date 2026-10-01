#!/usr/bin/env bash
# Linux only. Exports never go into Git, CI artifacts, or the application image.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ops_common.sh"
load_ops "$@"
exec 9>"$BACKUP_ROOT/$PROJECT.backup.lock"
flock -n 9 || die "A backup for this project is already running."

stamp=$(date -u +%Y%m%dT%H%M%SZ)-$RANDOM
folder="$BACKUP_ROOT/$PROJECT/$stamp"
mkdir -p "$folder"
echo "Creating PostgreSQL backup for $PROJECT..."
dc exec -T db sh -ec 'PGPASSWORD="$APP_DB_PASSWORD" pg_dump -h 127.0.0.1 -U "$APP_DB_USER" -d "$POSTGRES_DB" -Fc' > "$folder/database.dump.partial"
[[ -s "$folder/database.dump.partial" ]] || die "Empty dump; backup stopped."
dc exec -T db pg_restore --list < "$folder/database.dump.partial" > /dev/null
mv "$folder/database.dump.partial" "$folder/database.dump"
(cd "$folder" && sha256sum database.dump > database.dump.sha256)
printf 'Project: %s\nCreated UTC: %s\n' "$PROJECT" "$stamp" > "$folder/release.txt"
web_id=$(dc ps -q web)
if [[ -n "$web_id" ]]; then docker inspect --format 'App image: {{.Config.Image}}' "$web_id" >> "$folder/release.txt"; fi

echo "Uploading encrypted backup off-server..."
restic_cmd backup --host "$PROJECT" --tag salonops --tag "$PROJECT" "/backups/$PROJECT/$stamp"
touch "$folder/uploaded"
# Retention applies ONLY to this project's tagged snapshots, not other projects.
restic_cmd forget --host "$PROJECT" --tag "$PROJECT" --group-by host,tags \
    --keep-last 5 --keep-daily 14 --keep-weekly 8 --keep-monthly 6
# Forget removes snapshot references; weekly repository maintenance runs prune.
# Remove only our old, successfully uploaded local folders within this exact root.
for old in "$BACKUP_ROOT/$PROJECT"/*; do
    [[ -d "$old" && -f "$old/uploaded" ]] || continue
    [[ "$(basename "$old")" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9]+$ ]] || continue
    [[ "$(realpath -e "$old")" == "$BACKUP_ROOT/$PROJECT/"* ]] || die "Unexpected backup path."
    if [[ -n "$(find "$old/uploaded" -mtime +7 -print)" ]]; then rm -rf -- "$old"; fi
done
echo "Backup complete: $PROJECT/$stamp (local plus encrypted remote snapshot)."
