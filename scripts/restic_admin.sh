#!/usr/bin/env bash
# Initialise or maintain the remote repository; never prints environment secrets.
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ops_common.sh"
[[ $# == 6 ]] || die "Usage: ENV_FILE PROJECT COMPOSE_FILE BACKUP_ROOT RESTIC_ENV_FILE init|check|prune|snapshots"
action=$6
load_ops "${@:1:5}"
case "$action" in
    init|check) restic_cmd "$action" ;;
    snapshots) restic_cmd snapshots --host "$PROJECT" --tag "$PROJECT" ;;
    prune) restic_cmd prune ;; # Only use a repository dedicated to this environment.
    *) die "Unsupported repository command." ;;
esac
