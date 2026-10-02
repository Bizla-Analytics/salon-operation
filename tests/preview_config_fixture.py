"""Synthetic resolved Compose fixture for offline safety tests; no credentials."""

def preview_config(https=False):
    config = {
        'name': 'salonops-dev',
        'services': {
            'web': {
                'image': 'synthetic:testing', 'networks': {'default': None},
                'environment': {
                    'APP_ENV': 'private-preview', 'DEBUG': 'False',
                    'ALLOWED_HOSTS': 'localhost,127.0.0.1', 'CSRF_TRUSTED_ORIGINS': '',
                    'TRUST_PROXY_HEADERS': 'False', 'SECURE_SSL_REDIRECT': 'False',
                    'SESSION_COOKIE_SECURE': 'False', 'CSRF_COOKIE_SECURE': 'False',
                    'SECURE_HSTS_SECONDS': '0', 'SECURE_HSTS_INCLUDE_SUBDOMAINS': 'False',
                    'SECURE_HSTS_PRELOAD': 'False', 'POSTGRES_HOST': 'db',
                    'POSTGRES_PORT': '5432', 'POSTGRES_DB': 'salonops_dev',
                    'POSTGRES_USER': 'salonops_dev_app', 'AUTO_MIGRATE': 'false',
                    'CHECK_DEPLOY': 'false', 'SECRET_KEY': 'synthetic',
                    'POSTGRES_PASSWORD': 'synthetic', 'TIME_ZONE': 'Asia/Kolkata',
                },
                'ports': [{'host_ip': '127.0.0.1', 'published': '8000', 'target': 8000, 'protocol': 'tcp'}],
            },
            'db': {
                'image': 'postgres:17-alpine', 'networks': {'default': None},
                'environment': {
                    'POSTGRES_DB': 'salonops_dev', 'POSTGRES_USER': 'salonops_admin',
                    'POSTGRES_PASSWORD': 'synthetic-admin',
                    'APP_DB_USER': 'salonops_dev_app', 'APP_DB_PASSWORD': 'synthetic',
                },
                'volumes': [
                    {'type': 'volume', 'source': 'postgres_data', 'target': '/var/lib/postgresql/data'},
                    {'type': 'bind', 'source': '/opt/salonops-dev/deploy/postgres/10-create-app-user.sh',
                     'target': '/docker-entrypoint-initdb.d/10-create-app-user.sh', 'read_only': True},
                ],
            },
        },
        'volumes': {'postgres_data': {'name': 'salonops-dev-pgdata'}},
        'networks': {'default': {'name': 'salonops-dev_default'}},
    }
    if https:
        config['services']['web']['environment'].update({
            'APP_ENV': 'production',
            'ALLOWED_HOSTS': 'operations.shahinanalytics.com,localhost,127.0.0.1',
            'CSRF_TRUSTED_ORIGINS': 'https://operations.shahinanalytics.com',
            'TRUST_PROXY_HEADERS': 'True', 'SECURE_SSL_REDIRECT': 'True',
            'SESSION_COOKIE_SECURE': 'True', 'CSRF_COOKIE_SECURE': 'True',
            'SECURE_HSTS_SECONDS': '300', 'CHECK_DEPLOY': 'true',
        })
        config['services']['proxy'] = {
            'image': 'caddy:2-alpine', 'networks': {'default': None},
            'ports': [{'target': p, 'published': str(p), 'protocol': 'tcp'} for p in (80, 443)],
            'volumes': [
                {'type': 'bind', 'source': '/opt/salonops-dev/deploy/Caddyfile.test',
                 'target': '/etc/caddy/Caddyfile', 'read_only': True},
                {'type': 'volume', 'source': 'caddy_data', 'target': '/data'},
                {'type': 'volume', 'source': 'caddy_config', 'target': '/config'},
            ],
        }
        config['volumes'].update({
            'caddy_data': {'name': 'salonops-dev-caddy-data'},
            'caddy_config': {'name': 'salonops-dev-caddy-config'},
        })
    return config


if __name__ == '__main__':
    import json
    import sys
    print(json.dumps(preview_config(https=sys.argv[1:] == ['--https'])))
