#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

die() { echo "ERROR: $*" >&2; exit 1; }
load_ops() {
    [[ $# == 5 ]] || die "Usage: ENV_FILE PROJECT COMPOSE_FILE BACKUP_ROOT RESTIC_ENV_FILE"
    ENV_FILE=$(realpath -e "$1")
    PROJECT=$2
    [[ "$PROJECT" =~ ^[a-z0-9][a-z0-9_-]+$ ]] || die "Invalid fixed Compose project name."
    COMPOSE_FILE=$(realpath -e "$3")
    mkdir -p "$4"
    BACKUP_ROOT=$(realpath -e "$4")
    [[ "$BACKUP_ROOT" != / ]] || die "BACKUP_ROOT must not be /"
    parent="$BACKUP_ROOT"
    while [[ "$parent" != / ]]; do
        [[ ! -e "$parent/.git" ]] || die "Keep backups outside Git checkouts."
        parent=$(dirname "$parent")
    done
    RESTIC_ENV_FILE=$(realpath -e "$5")
    # Do not silently treat a backup on this VPS's disk as an off-server backup.
    grep -Eq '^RESTIC_REPOSITORY=(s3:https://|rest:https://)' "$RESTIC_ENV_FILE" || die "Configure an off-server HTTPS Restic repository."
}
dc() {
    SALONOPS_ENV_FILE="$ENV_FILE" docker compose --env-file "$ENV_FILE" -p "$PROJECT" -f "$COMPOSE_FILE" "$@"
}
restic_cmd() {
    docker run --rm --env-file "$RESTIC_ENV_FILE" \
        --mount "type=bind,source=$BACKUP_ROOT,target=/backups" \
        "${RESTIC_IMAGE:-restic/restic:0.19.1}" --no-cache "$@"
}
