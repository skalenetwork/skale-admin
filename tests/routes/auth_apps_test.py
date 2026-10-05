"""Exercise real route registration and request teardown without external services."""

import importlib.util
import tempfile
import unittest
from contextlib import ExitStack
from dataclasses import make_dataclass
from enum import Enum
from pathlib import Path
from unittest.mock import Mock, patch

TOKEN = 'ab' * 32


class APIAuthApplicationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        root = Path(cls.stack.enter_context(tempfile.TemporaryDirectory()))
        cls.token_path = root / 'auth' / 'admin-api.token'
        cls.token_path.parent.mkdir(mode=0o700)
        cls.token_path.write_text(TOKEN + '\n')
        cls.token_path.chmod(0o600)

        # skale-contracts fetches metadata and statsd opens a socket at import time.
        cls.stack.enter_context(patch('requests.get', return_value=Mock(text='{"networks": []}')))
        cls.stack.enter_context(patch('statsd.StatsClient'))
        cls.stack.enter_context(
            patch('tools.constants.NODE_OPTIONS_FILEPATH', root / 'options.json')
        )
        cls.stack.enter_context(patch('tools.logger.init_api_logger'))
        cls.stack.enter_context(
            patch('skale_core.settings.get_internal_settings', return_value=Mock())
        )

        from web import auth

        cls.stack.enter_context(patch.object(auth, 'ADMIN_API_TOKEN_PATH', cls.token_path))
        with patch('tools.helper.is_passive', return_value=False):
            import fair_api
            import skale_api

        with patch('tools.helper.is_passive', return_value=True):
            spec = importlib.util.spec_from_file_location('passive_auth_api', fair_api.__file__)
            passive_api = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(passive_api)

        cls.apis = [skale_api, fair_api, passive_api]
        for api in cls.apis:
            api.app.testing = True

    def test_all_state_changing_routes_require_credentials(self):
        public_post_endpoints = {
            'fair-staking.get_earned_fee_amount',
            'fair-staking.get_exit_requests',
        }
        checked = 0
        for api in self.apis:
            with patch.object(api, 'wait_until_admin_inited') as wait:
                for rule in api.app.url_map.iter_rules():
                    methods = rule.methods & {'POST', 'PUT', 'PATCH', 'DELETE'}
                    if not methods or rule.endpoint in public_post_endpoints:
                        continue
                    for method in methods:
                        with self.subTest(api=api.__name__, route=rule.rule, method=method):
                            response = api.app.test_client().open(rule.rule, method=method, json={})
                            self.assertEqual(response.status_code, 401)
                            self.assertEqual(response.json['status'], 'error')
                            checked += 1
                wait.assert_not_called()
        self.assertGreater(checked, 0)

    def test_operator_get_and_head_routes_require_credentials(self):
        for api in self.apis:
            routes = ['/api/v1/info/sgx-options', '/api/v1/info/sgx-certificates']
            if api is self.apis[0]:
                routes.append('/api/v1/node/signature')
            with patch.object(api, 'wait_until_admin_inited') as wait:
                for route in routes:
                    for method in ('GET', 'HEAD'):
                        with self.subTest(api=api.__name__, route=route, method=method):
                            response = api.app.test_client().open(route, method=method)
                            self.assertEqual(response.status_code, 401)
                wait.assert_not_called()

    def test_missing_server_token_fails_closed_with_safe_teardown(self):
        self.token_path.unlink()
        try:
            for api in self.apis:
                with self.subTest(api=api.__name__):
                    with patch.object(api, 'wait_until_admin_inited') as wait:
                        response = api.app.test_client().post('/api/v1/ssl/upload')
                        self.assertEqual(response.status_code, 503)
                        wait.assert_not_called()
        finally:
            self.token_path.write_text(TOKEN + '\n')
            self.token_path.chmod(0o600)

    def test_authenticated_sgx_options_delegate_to_sgx(self):
        from web.routes import info

        # Exercise nested dataclass/enum serialization as returned by the SGX SDK.
        level = Enum('Level', {'INFO': 2})
        flags = make_dataclass('Flags', ['auto_sign', 'log_level'])(False, level.INFO)
        options = make_dataclass('Options', ['flags', 'build'])(flags, None)
        for api in self.apis[:2]:
            with self.subTest(api=api.__name__), ExitStack() as stack:
                stack.enter_context(patch.object(api, 'wait_until_admin_inited'))
                stack.enter_context(patch.object(api, 'NodeConfig'))
                stack.enter_context(
                    patch.object(api, 'get_settings', return_value=Mock(sgx_url='https://sgx:1026'))
                )
                stack.enter_context(patch.object(api, 'DockerUtils'))
                if hasattr(api, 'get_database'):
                    stack.enter_context(patch.object(api, 'get_database'))
                client = stack.enter_context(patch.object(info, 'SgxClient'))
                client.return_value.get_server_options.return_value = options
                response = api.app.test_client().get(
                    '/api/v1/info/sgx-options', headers={'Authorization': f'Bearer {TOKEN}'}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json,
                    {
                        'status': 'ok',
                        'payload': {'flags': {'auto_sign': False, 'log_level': 2}, 'build': None},
                    },
                )
                client.assert_called_once_with(
                    'https://sgx:1026', info.SGX_CERTIFICATES_FOLDER, allow_registration=False
                )
                client.return_value.get_server_options.assert_called_once_with()

                client.return_value.get_server_options.side_effect = info.SgxError(
                    'SGX unavailable'
                )
                response = api.app.test_client().get(
                    '/api/v1/info/sgx-options', headers={'Authorization': f'Bearer {TOKEN}'}
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json, {'status': 'error', 'payload': 'SGX unavailable'})

    def test_valid_credentials_reach_resources_and_handler(self):
        for api in self.apis:
            with self.subTest(api=api.__name__), ExitStack() as stack:
                wait = stack.enter_context(patch.object(api, 'wait_until_admin_inited'))
                stack.enter_context(patch.object(api, 'NodeConfig'))
                stack.enter_context(patch.object(api, 'get_settings'))
                stack.enter_context(patch.object(api, 'DockerUtils'))
                if hasattr(api, 'get_database'):
                    stack.enter_context(patch.object(api, 'get_database'))
                original = api.app.view_functions['ssl.upload']
                handler = Mock(return_value={'status': 'ok', 'payload': {}})
                handler.cli_only = original.cli_only
                stack.enter_context(patch.dict(api.app.view_functions, {'ssl.upload': handler}))
                response = api.app.test_client().post(
                    '/api/v1/ssl/upload', headers={'Authorization': f'Bearer {TOKEN}'}
                )
                self.assertEqual(response.status_code, 200)
                wait.assert_called_once()
                handler.assert_called_once()


if __name__ == '__main__':
    unittest.main()
