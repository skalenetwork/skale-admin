import logging
from unittest import mock

from skale_core.settings import SkaleSettings

from tools.logger import ADMIN_LOG_FORMAT, HidingFormatter, compose_hiding_patterns


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
