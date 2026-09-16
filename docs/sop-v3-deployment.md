# Grouped tasks and V3 rollout

## Staff workflow

V3 imports optional `supports_waiting` and `staff_instructions` columns from Task
Master. Both are copied into new visit task snapshots. V1/V2 imports remain
compatible. Existing task snapshots are not rewritten by imports or migrations.

A processing-enabled card uses Start, Start Waiting, Resume, Complete. Removal
and finishing remain instructions within that card. Actual hands-on and waiting
intervals are recorded separately; master standard minutes are not overwritten.
Waiting uses elapsed time, not a product-specific countdown or an alarm.
An employee can work on another visit during waiting, but only one hands-on task
can run at a time. Service order within each visit is still enforced. Resource
occupancy/reservations are not implemented by this change.

The completion of a grouped card confirms all its instructions, not separately
audited substeps. Waiting may repeat. Complete is available while hands-on; a
waiting task must be resumed before completion. Skipping is only for pending,
skippable tasks. Cancel/reassign closes timing intervals and preserves history.

## Before importing

- Keep the frozen V2 workbook and checksum unchanged and outside Git.
- Review the V3 workbook audit stored alongside the workbook. Some original
  service standards and quantities remain unverified. In particular new pack
  quantities must be supplied; inactive/unconfirmed mappings are not a valid
  consumption/cost baseline. Passive zero on a new cleanup card means the standard
  is unconfirmed, not that setting should be omitted.
- Confirm the target host and take a database backup plus the current code/image
  version. Do not reset production or close abandoned tasks in bulk.
- Coordinate maintenance with staff. Unfinished tasks are not proof staff are
  online; preserve them unless a manager makes a specific correction.

## Local checks / rollout

```sh
docker compose up --build -d
docker compose exec -T web python manage.py check
docker compose exec -T web python manage.py test
docker compose exec -T web python manage.py makemigrations --check --dry-run
docker compose exec -T web python manage.py import_sop_workbook data/Service_Operation_SOP_V3_2026-09-06.xlsx --dry-run
docker compose exec -T web python manage.py import_sop_workbook data/Service_Operation_SOP_V3_2026-09-06.xlsx
```

The entrypoint runs additive migrations on startup. Deploy compatible code and
schema before importing V3. Test /health/, an authorised employee execution page,
and manager verification. Confirm import does not change VisitTask rows and that
reimport keeps master record counts stable. Existing pending plans retain their
snapshots; deliberately rebuilding a wholly unstarted visit is a separate manager
action, never an automatic bulk import side effect.

## Rollback

Keep the additive schema and V3-compatible application available once any WAITING
task exists. Old code does not understand WAITING. Reimporting V2 does not remove
V3-only rows, so it is not a complete rollback. Restore the predeployment database
and code only during coordinated maintenance and only if that will not discard
new staff work; otherwise forward-fix while preserving task/timing history.
