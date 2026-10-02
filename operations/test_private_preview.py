from copy import deepcopy
import importlib.util

from django.conf import settings
from django.test import SimpleTestCase


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, settings.BASE_DIR / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validate = load_module('preview_validator', 'scripts/validate_preview.py').validate
preview_config = load_module('preview_fixture', 'tests/preview_config_fixture.py').preview_config


class PrivatePreviewConfigTests(SimpleTestCase):
    def test_fixed_private_test_configuration_is_accepted(self):
        validate(preview_config())

    def test_empty_compose_v5_ipam_is_accepted(self):
        config = preview_config()
        config['networks']['default']['ipam'] = {}
        validate(config)

    def test_production_resources_or_public_network_access_are_rejected(self):
        changes = [
            lambda c: c.update(name='salonops-prod'),
            lambda c: c['volumes']['postgres_data'].update(name='salonops-prod-pgdata'),
            lambda c: c['volumes']['postgres_data'].update(external=True),
            lambda c: c['services']['web']['ports'][0].update(host_ip='0.0.0.0'),
            lambda c: c['services']['db'].update(ports=[{'published': '5432'}]),
            lambda c: c['services']['web'].update(network_mode='host'),
            lambda c: c['services']['db'].update(privileged=True),
            lambda c: c['services']['db']['environment'].update(POSTGRES_DB='salon_operations'),
            lambda c: c['services']['web']['environment'].update(POSTGRES_HOST='production-db'),
            lambda c: c['services']['web']['environment'].update(DEBUG='True'),
            lambda c: c['services']['web']['environment'].update(POSTGRES_ADMIN_PASSWORD='secret'),
            lambda c: c['services'].update(caddy={}),
            lambda c: c['networks']['default'].update(driver_opts={'gateway_mode_ipv4': 'routed'}),
            lambda c: c['services']['web'].update(volumes=[{'source': '/etc'}]),
        ]
        for change in changes:
            with self.subTest(change=change):
                config = deepcopy(preview_config())
                change(config)
                with self.assertRaises(ValueError):
                    validate(config)
