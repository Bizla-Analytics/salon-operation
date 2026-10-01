#!/bin/sh
set -eu
# Only executed by the PostgreSQL image when its data directory is EMPTY.
[ "$APP_DB_USER" != "$POSTGRES_USER" ] || { echo "App user must differ from the bootstrap superuser." >&2; exit 1; }
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
    --set=app_user="$APP_DB_USER" --set=app_password="$APP_DB_PASSWORD" --set=db_name="$POSTGRES_DB" <<'SQL'
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER DATABASE :"db_name" OWNER TO :"app_user";
GRANT USAGE, CREATE ON SCHEMA public TO :"app_user";
SQL
