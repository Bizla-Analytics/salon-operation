from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Reject SQLite and PostgreSQL superuser/database-role-administrator app accounts.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            raise CommandError('Only PostgreSQL is supported.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=current_user')
            privileges = cursor.fetchone()
        if not privileges or any(privileges):
            raise CommandError('The application DB account must be NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION.')
        self.stdout.write(self.style.SUCCESS('Restricted PostgreSQL application role: OK'))
