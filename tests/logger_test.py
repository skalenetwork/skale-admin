import importlib.util
import logging
import sys
from unittest import mock

import pytest
from skale_core.settings import SkaleSettings

from tools.logger import (
    ADMIN_LOG_FORMAT,
    API_LOG_FORMAT,
    HidingFormatter,
    compose_hiding_patterns,
)


def test_custom_formatter(st: SkaleSettings):
    sgx_endpoint = 'https://123.123.123.123:1026'
    eth_endpoint = 'http://endpoint.com:8545'
    text = (
        'NEK:2felkfl12k31kn3lk2r3n12jl2k4hn12l54n2l2, '
        'http://endpoint.com:8545, '
        'https://endpoint.com:8545, '
        'https://endpoint.com:1111, '
        'https://123.123.123.123:1026, '
        'localhost '
        'http://localhost:8080, '
        'https://endpoint.om:8545, '
        'https://endoint.om:2321, '
        'https://testnet.com, '
        'wss://127.0.0.1.com, '
        'ttt://127.0.0.1.com, '
        'NEK//127.0.0.1.com, '
    )
    record = logging.makeLogRecord({'msg': text})

    sgx_endpoint = 'https://123.123.123.123:1026'
    eth_endpoint = 'http://endpoint.com:8545'
    st_override = st.model_copy(update={'sgx_url': sgx_endpoint, 'endpoint': eth_endpoint})

    with (
        mock.patch('tools.logger.get_settings', return_value=st_override),
    ):
        formatted_text = HidingFormatter(ADMIN_LOG_FORMAT, compose_hiding_patterns()).format(record)
        assert (
            'None:0 - [SGX_KEY], http://[ETH_IP]:8545, https://[ETH_IP]:8545, https://[ETH_IP]:1111, https://[SGX_IP]:1026, localhost http://localhost:8080, https://endpoint.om:8545, https://endoint.om:2321, https://testnet.com, wss://127.0.0.1.com, ttt://127.0.0.1.com, NEK//127.0.0.1.com, '  # noqa
            in formatted_text
        )

    # local eth endpoint
    formatted_text = HidingFormatter(ADMIN_LOG_FORMAT, compose_hiding_patterns()).format(record)
    assert (
        'None:0 - [SGX_KEY], http://endpoint.com:8545, https://endpoint.com:8545, https://endpoint.com:1111, https://123.123.123.123:1026, localhost http://localhost:8080, https://endpoint.om:8545, https://endoint.om:2321, https://testnet.com, wss://127.0.0.1.com, ttt://127.0.0.1.com, NEK//127.0.0.1.com,'  # noqa
        in formatted_text
    )


def test_url_secrets_hidden(st: SkaleSettings):
    sgx_endpoint = 'https://123.123.123.123:1026'
    eth_endpoint = 'https://svc.provider.com/v3/abcdefabcdefabcdefabcdef?auth=topsecretauthvalue'
    text = (
        'https://svc.provider.com/v3/abcdefabcdefabcdefabcdef?auth=topsecretauthvalue, '
        'bare key topsecretauthvalue, '
        'bare segment abcdefabcdefabcdefabcdef, '
        'https://other.provider.io/?apikey=anotherforeignkey, '
        'short path https://svc.provider.com/eth/mainnet'
    )
    record = logging.makeLogRecord({'msg': text})
    st_override = st.model_copy(update={'sgx_url': sgx_endpoint, 'endpoint': eth_endpoint})

    with (
        mock.patch('tools.logger.get_settings', return_value=st_override),
    ):
        formatted_text = HidingFormatter(ADMIN_LOG_FORMAT, compose_hiding_patterns()).format(record)

    assert 'topsecretauthvalue' not in formatted_text
    assert 'abcdefabcdefabcdefabcdef' not in formatted_text
    assert 'anotherforeignkey' not in formatted_text
    assert (
        'https://[ETH_IP]/v3/[ETH_PATH_SEGMENT]?[ETH_QUERY], '
        'bare key [ETH_QUERY_VALUE], '
        'bare segment [ETH_PATH_SEGMENT], '
        'https://other.provider.io/?apikey=[HIDDEN], '
        'short path https://[ETH_IP]/eth/mainnet'
        in formatted_text
    )


@pytest.mark.parametrize('api_name', ['skale_api', 'fair_api'])
def test_api_error_logged_once(api_name, caplog, capsys):
    # the levels match init_logger
    caplog.set_level(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(HidingFormatter(API_LOG_FORMAT, {'secretvalue': '[HIDDEN]'}))
    origin = importlib.util.find_spec(api_name).origin
    spec = importlib.util.spec_from_file_location(f'fresh_{api_name}', origin)
    api = importlib.util.module_from_spec(spec)
    with (
        mock.patch.object(logging.getLogger(), 'handlers', [handler]),
        mock.patch('tools.logger.init_api_logger'),
        mock.patch('tools.helper.is_passive', return_value=False),
        mock.patch('skale_core.settings.get_internal_settings'),
    ):
        spec.loader.exec_module(api)
        error = ValueError('secretvalue')
        with mock.patch.object(api, 'wait_until_admin_inited', side_effect=error):
            response = api.app.test_client().get('/api/v1/info/hardware')

    output = capsys.readouterr().err
    assert response.status_code == 500
    assert 'secretvalue' not in output
    assert output.count('Exception on /api/v1/info/hardware [GET]') == 1
    assert output.count('Traceback (most recent call last)') == 1
