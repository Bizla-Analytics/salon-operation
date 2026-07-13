# Salon Operation project guidance

This repository is a standalone Django project. Treat `/home/shahin/Salon_Operation`
as the project root and do not read from or modify neighboring projects unless the
user explicitly requests it.

## Environment

- Use the project-local virtual environment at `.venv`.
- Run Python with `.venv/bin/python` and pip with `.venv/bin/pip` when the shell is
  not activated.
- Dependencies are declared in `requirements.txt`.
- Local development uses SQLite in `db.sqlite3`.
- Environment variable examples are documented in `.env.example`; never commit a
  real `.env` or secrets.

## Application structure

- `salonops/`: Django project configuration, URLs, WSGI, and ASGI.
- `operations/`: application models, forms, views, URLs, admin, and migrations.
- `templates/`: shared and feature templates.
- `static/`: source static assets.
- `sample_csv/`: example import data.

## Verification

After Python changes, run the relevant checks from the project root:

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py test
```

Do not modify `db.sqlite3`, generate migrations, seed data, or run destructive
database commands unless the requested task requires it.

