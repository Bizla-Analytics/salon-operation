#!/usr/bin/env bash
# Separate DEV path: production's mandatory off-server load_ops is unchanged.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ops_common.sh"

load_preview() {
    [[ $# == 4 ]] || die "Usage: ENV_FILE salonops-dev COMPOSE_FILE BACKUP_ROOT"
    [[ "$2" == salonops-dev ]] || die "Private preview is restricted to salonops-dev."
    PROJECT=$2
    ENV_FILE=$(realpath -e "$1")
    [[ "$(stat -c %a "$ENV_FILE")" == 600 || "$(stat -c %a "$ENV_FILE")" == 400 ]] || die "The preview env file must have mode 600 or 400."
    COMPOSE_FILE=$(realpath -e "$3")
    [[ "$(basename "$COMPOSE_FILE")" == compose.preview.yaml ]] || die "Use standalone compose.preview.yaml."
    mkdir -p "$4"
    BACKUP_ROOT=$(realpath -e "$4")
    [[ "$BACKUP_ROOT" != / ]] || die "BACKUP_ROOT must not be /"
    for path in "$BACKUP_ROOT" "$(dirname "$ENV_FILE")"; do
        while [[ "$path" != / ]]; do
            [[ ! -e "$path/.git" ]] || die "Keep preview credentials and backups outside Git checkouts."
            path=$(dirname "$path")
        done
    done
    chmod 700 "$BACKUP_ROOT"
    if [[ -z "${SALONOPS_IMAGE:-}" ]]; then
        [[ -f "$BACKUP_ROOT/$PROJECT.last-successful-image" ]] || die "No successful release yet; first deploy through the dev workflow."
        export SALONOPS_IMAGE=$(cat "$BACKUP_ROOT/$PROJECT.last-successful-image")
    fi
    # Validate effective configuration BEFORE touching any container or volume.
    dc config --format json | python3 "$(dirname "${BASH_SOURCE[0]}")/validate_preview.py"
}
