# SalonOps — Django Salon SOP & Service Workflow

A responsive Django application for salon operations with separate admin, manager, employee, and customer-feedback experiences.

## Included

- Multi-branch master data and branch-isolated manager/employee access
- Admin CRUD through Django Admin
- CSV insert/update import for branches, chairs, services, and SOP tasks
- Admin creation of managers and employees by branch
- Manager visit creation, service assignment, chair allocation, live progress, verification, invoicing, and feedback handoff
- Employee mobile workflow showing one current task with large Start, Complete, and Skip controls
- Flexible SOP phases: Before, During, Finishing, and After service
- SOP task categories for consultation, service steps, towel/laundry, cleaning/sanitization, quality checks, and recommendations
- Required, optional, and skippable tasks with skip reasons
- Five-question emoji feedback form with optional suggestion
- SQLite development database and PostgreSQL-ready dependency set

## Quick start

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Run `seed_demo` only when setting up development demo data. Do not run it during
normal application startup or production deployments because it resets the demo
accounts and demo SOP configuration.

Open `http://127.0.0.1:8000/`.

## Demo accounts

All demo passwords are `Admin@123`.

| Role | Username |
|---|---|
| Admin | `admin` |
| Manager | `manager` |
| Employee | `stylist` |

Change all passwords before real use.

## Main URLs

- `/` — role-aware dashboard
- `/admin/` — full Django CRUD administration
- `/admin-panel/` — simplified admin landing page
- `/manager/` — manager live operations
- `/employee/` — employee work list

## CSV import

Use **Admin panel → CSV master-data import**. Import in this order:

1. `branches.csv`
2. `chairs.csv`
3. `services.csv`
4. `sop_tasks.csv`

Sample files are in `sample_csv/`. Imports use update-or-create behaviour, so matching codes/sequences are updated rather than duplicated.

### Accepted SOP values

- `phase`: `BEFORE`, `DURING`, `FINISHING`, `AFTER`
- `task_type`: `SERVICE`, `CONSULT`, `HYGIENE`, `TOWEL`, `QUALITY`, `RECOMMEND`
- Boolean values: `true/false`, `yes/no`, or `1/0`

## Employee-effort design

The employee sees only their assigned jobs. Inside a job, the page shows one current SOP task and large action buttons. Notes are optional except when a configured skipped task requires a reason. The full checklist is collapsed by default.

## Production notes

- Set a secure `SECRET_KEY`, `DEBUG=False`, and explicit `ALLOWED_HOSTS`.
- Keep `salon_db.sqlite3` outside Git-managed deployment files and back it up
  before every deployment. The database is intentionally ignored by Git.
- Replace SQLite with PostgreSQL for real multi-user deployment.
- Serve with Gunicorn and Nginx, or deploy to a Django-capable host.
- Add HTTPS before using customer or employee data.
- Create separate production admin credentials and deactivate demo accounts.

## Useful commands

```bash
python manage.py check
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```
