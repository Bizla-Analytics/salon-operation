from django.conf import settings
from django.core import checks
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Fail on deployment warnings except the two deliberately opt-in HSTS policies.'

    def handle(self, *args, **options):
        if settings.DEBUG:
            raise CommandError('Production security checks require DEBUG=False.')
        messages = checks.run_checks(include_deployment_checks=True)
        # Applying these to a company domain without knowing its other subdomains
        # can break unrelated sites. They remain visible, not globally silenced.
        optional = {'security.W005', 'security.W021'}
        failures = [m for m in messages if m.level >= checks.WARNING and m.id not in optional]
        for message in messages:
            self.stdout.write(str(message))
        if failures:
            raise CommandError('Deployment security checks failed.')
        self.stdout.write(self.style.SUCCESS('HTTPS security checks passed; subdomain/preload HSTS remains opt-in.'))
