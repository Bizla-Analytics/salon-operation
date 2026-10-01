#!/usr/bin/env bash
# No production connection, mounts, ports, or networks. Never restores into 'db'.
set -Eeuo pipefail
umask 077
[[ $# == 1 ]] || { echo "Usage: restore_rehearsal.sh /absolute/path/database.dump" >&2; exit 1; }
dump=$(realpath -e "$1")
[[ -s "$dump" ]] || { echo "Missing or empty dump." >&2; exit 1; }
if [[ -f "$dump.sha256" ]]; then (cd "$(dirname "$dump")" && sha256sum --check "$(basename "$dump").sha256"); fi
name="salonops-rehearsal-$(date -u +%Y%m%d%H%M%S)-$RANDOM"
created=false
cleanup() {
    if [[ "$created" == true && "$name" =~ ^salonops-rehearsal-[0-9]+-[0-9]+$ ]]; then docker rm -f -v "$name" > /dev/null; fi
}
trap cleanup EXIT
password=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
docker run -d --name "$name" --network none \
    -e POSTGRES_DB=salonops_rehearsal -e POSTGRES_USER=rehearsal_user -e POSTGRES_PASSWORD="$password" \
    "${POSTGRES_IMAGE:-postgres:17-alpine}" > /dev/null
created=true
ready=false
for i in $(seq 1 60); do
    if docker exec "$name" pg_isready -U rehearsal_user -d salonops_rehearsal > /dev/null 2>&1; then ready=true; break; fi
    sleep 1
done
[[ "$ready" == true ]] || { echo "Isolated PostgreSQL did not become ready." >&2; exit 1; }
docker cp "$dump" "$name:/tmp/database.dump"
docker exec "$name" pg_restore --exit-on-error --no-owner --no-acl -U rehearsal_user -d salonops_rehearsal /tmp/database.dump
# Abort if the backup lacks the expected application schema. Counts expose no records.
docker exec "$name" psql -v ON_ERROR_STOP=1 -U rehearsal_user -d salonops_rehearsal -c \
    'SELECT count(*) AS migration_rows FROM django_migrations; SELECT count(*) AS visits FROM operations_visit; SELECT count(*) AS tasks FROM operations_visittask; SELECT count(*) AS timing_segments FROM operations_tasktimingsegment; SELECT count(*) AS invoices FROM operations_invoice; SELECT count(*) AS feedback FROM operations_feedback;'
echo "Restore rehearsal PASSED. Isolated database will now be removed; production was not accessed."
