import logging

from tools.logger import compose_hiding_patterns, HidingFormatter, ADMIN_LOG_FORMAT


def test_custom_formatter():
    text = (
        'NEK:2felkfl12k31kn3lk2r3n12jl2k4hn12l54n2l2, '
        'http://54.545.454.12:1231, '
        'localhost '
        'http://localhost:8080, '
        'localhostlocalhostloc '
        'https://testnet.com, '
        'wss://127.0.0.1.com, '
        'ttt://127.0.0.1.com, '
        'foo://127.0.0.1.com, '
        'NEK//127.0.0.1.com, '
    )
    record = logging.makeLogRecord({'msg': text})

    formatted_text = HidingFormatter(
        ADMIN_LOG_FORMAT,
        compose_hiding_patterns()
    ).format(record)
    assert 'MainThread - None:0 - [SGX_KEY], http://54.545.454.12:1231, [ETH_IP] http://[ETH_IP]:8080, [ETH_IP][ETH_IP]loc https://testnet.com, wss://127.0.0.1.com, ttt://127.0.0.1.com, foo://127.0.0.1.com, NEK//127.0.0.1.com, ' in formatted_text
