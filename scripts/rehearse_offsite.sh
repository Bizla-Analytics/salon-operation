#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/ops_common.sh"
load_ops "$@"
exec 9>"$BACKUP_ROOT/$PROJECT.rehearsal.lock"
flock -n 9 || die "A restore rehearsal is already running."
restore_dir=$(mktemp -d "$BACKUP_ROOT/rehearsal-$PROJECT-XXXXXX")
cleanup() {
    [[ "$(realpath -e "$restore_dir")" == "$BACKUP_ROOT/rehearsal-$PROJECT-"* ]] || return
    rm -rf -- "$restore_dir"
}
trap cleanup EXIT
restic_cmd restore latest --host "$PROJECT" --tag "$PROJECT" --target "/backups/$(basename "$restore_dir")" --verify
mapfile -t dumps < <(find "$restore_dir" -type f -name database.dump)
[[ ${#dumps[@]} == 1 ]] || die "Expected exactly one database dump in the selected snapshot."
bash "$(dirname "${BASH_SOURCE[0]}")/restore_rehearsal.sh" "${dumps[0]}"
restic_cmd check
