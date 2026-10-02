import io
import json
import os
import subprocess
import sys
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import checks
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


class ProductionSettingsTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_security_check_allows_only_deliberate_hsts_policy_warnings(self):
        target = 'operations.management.commands.check_production_security.checks.run_checks'
        with patch(target, return_value=[checks.Warning('Opt-in', id='security.W005'),
                                         checks.Warning('Opt-in', id='security.W021')]):
            call_command('check_production_security', stdout=io.StringIO())
        with patch(target, return_value=[checks.Warning('Unsafe', id='security.W012')]):
            with self.assertRaises(CommandError):
                call_command('check_production_security', stdout=io.StringIO())

    def settings_process(self, changes=None, remove=()):
        env = {
            'PATH': os.environ.get('PATH', ''), 'APP_ENV': 'production', 'DEBUG': 'False',
            'SECRET_KEY': 'production-settings-test-only-not-a-real-key-1234567890ABCDEF',
            'ALLOWED_HOSTS': 'salon.example.com,localhost,127.0.0.1',
            'CSRF_TRUSTED_ORIGINS': 'https://salon.example.com',
            'POSTGRES_HOST': 'db', 'POSTGRES_DB': 'test_db', 'POSTGRES_USER': 'test_app',
            'POSTGRES_PASSWORD': 'synthetic-test-password',
        }
        env.update(changes or {})
        for name in remove:
            env.pop(name, None)
        return subprocess.run([sys.executable, '-c',
            'import json; from salonops import settings as s; print(json.dumps({'
            '"engine":s.DATABASES["default"]["ENGINE"], "redirect":s.SECURE_SSL_REDIRECT,'
            '"session_secure":s.SESSION_COOKIE_SECURE,"csrf_secure":s.CSRF_COOKIE_SECURE,'
            '"proxy":s.SECURE_PROXY_SSL_HEADER,"hsts":s.SECURE_HSTS_SECONDS}))'],
            env=env, capture_output=True, text=True, timeout=20)

    def test_production_defaults_are_postgresql_and_https_only(self):
        process = self.settings_process()
        self.assertEqual(process.returncode, 0, process.stderr)
        config = json.loads(process.stdout)
        self.assertEqual(config['engine'], 'django.db.backends.postgresql')
        self.assertTrue(config['redirect'])
        self.assertTrue(config['session_secure'])
        self.assertTrue(config['csrf_secure'])
        self.assertEqual(config['hsts'], 300)
        self.assertIsNone(config['proxy'])

    def test_proxy_trust_is_explicit_and_local_http_remains_available(self):
        process = self.settings_process({'TRUST_PROXY_HEADERS': 'True'})
        self.assertEqual(json.loads(process.stdout)['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        process = self.settings_process({'APP_ENV': 'development', 'DEBUG': 'True'})
        config = json.loads(process.stdout)
        self.assertFalse(config['redirect'])
        self.assertFalse(config['session_secure'])

    def test_missing_pg_configuration_never_falls_back_to_sqlite(self):
        for name in ['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']:
            with self.subTest(name=name):
                process = self.settings_process(remove=[name])
                self.assertNotEqual(process.returncode, 0)
                self.assertIn(name + ' is required', process.stderr)

    def test_insecure_production_configuration_fails_closed(self):
        for changes in [
            {'DEBUG': 'True'}, {'SECRET_KEY': 'short'}, {'ALLOWED_HOSTS': '*'},
            {'CSRF_TRUSTED_ORIGINS': 'http://salon.example.com'},
            {'SECURE_SSL_REDIRECT': 'False'}, {'SESSION_COOKIE_SECURE': 'False'},
            {'CSRF_COOKIE_SECURE': 'False'}, {'TRUST_PROXY_HEADERS': 'invalid'},
        ]:
            with self.subTest(changes=changes):
                self.assertNotEqual(self.settings_process(changes).returncode, 0)

    def preview_settings(self, changes=None):
        config = {
            'APP_ENV': 'private-preview', 'DEBUG': 'False',
            'ALLOWED_HOSTS': 'localhost,127.0.0.1', 'CSRF_TRUSTED_ORIGINS': '',
            'SECURE_SSL_REDIRECT': 'False', 'SESSION_COOKIE_SECURE': 'False',
            'CSRF_COOKIE_SECURE': 'False', 'SECURE_HSTS_SECONDS': '0',
            'TRUST_PROXY_HEADERS': 'False',
        }
        config.update(changes or {})
        return self.settings_process(config)

    def test_private_preview_is_non_debug_postgresql_with_local_http(self):
        process = self.preview_settings()
        self.assertEqual(process.returncode, 0, process.stderr)
        config = json.loads(process.stdout)
        self.assertEqual(config['engine'], 'django.db.backends.postgresql')
        self.assertFalse(config['redirect'])
        self.assertFalse(config['session_secure'])
        self.assertFalse(config['csrf_secure'])
        self.assertEqual(config['hsts'], 0)
        self.assertIsNone(config['proxy'])

    def test_private_preview_rejects_debug_public_hosts_and_proxy_trust(self):
        for changes in [
            {'DEBUG': 'True'}, {'ALLOWED_HOSTS': '*'},
            {'ALLOWED_HOSTS': 'localhost,127.0.0.1,203.0.113.10'},
            {'CSRF_TRUSTED_ORIGINS': 'https://salon.example.com'},
            {'TRUST_PROXY_HEADERS': 'True'}, {'SECURE_HSTS_SECONDS': '300'},
            {'SESSION_COOKIE_SECURE': 'True'},
        ]:
            with self.subTest(changes=changes):
                self.assertNotEqual(self.preview_settings(changes).returncode, 0)

    def test_private_preview_flags_do_not_bypass_production_security(self):
        self.assertNotEqual(self.preview_settings({'APP_ENV': 'production'}).returncode, 0)

    def test_database_security_command_rejects_server_administrator_roles(self):
        with patch('operations.management.commands.check_database_security.connection') as connection:
            connection.vendor = 'postgresql'
            cursor = connection.cursor.return_value.__enter__.return_value
            for privileges in [(True, False, False, False), (False, True, False, False),
                               (False, False, True, False), (False, False, False, True)]:
                cursor.fetchone.return_value = privileges
                with self.assertRaises(CommandError):
                    call_command('check_database_security', stdout=io.StringIO())
            cursor.fetchone.return_value = (False, False, False, False)
            output = io.StringIO()
            call_command('check_database_security', stdout=output)
            self.assertIn('application role: OK', output.getvalue())


@override_settings(
    SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'),
    SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True,
    STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class HTTPSRequestTests(TestCase):
    def test_http_redirects_but_trusted_proxy_https_does_not_loop(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.url.startswith('https://'))
        response = self.client.get(reverse('login'), HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies['csrftoken']['secure'])
        self.assertEqual(self.client.get(reverse('health')).status_code, 200)

    def test_login_sets_a_secure_http_only_session_cookie(self):
        User.objects.create_user('https_test', password='Synthetic-test-password!27')
        response = self.client.post(reverse('login'), {
            'username': 'https_test', 'password': 'Synthetic-test-password!27',
        }, secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.cookies['sessionid']['secure'])
        self.assertTrue(response.cookies['sessionid']['httponly'])
