from tools.logger import HidingFormatter, HIDING_PATTERNS


def test_custom_formatter():
    class BaseFormatter:
        def __init__(self):
            pass

        def format(self, record):
            return record

    text = (
        'NEK:2felkfl12k31kn3lk2r3n12jl2k4hn12l54n2l2, '
        'http://54.545.454.12:1231, '
        'http://localhost:8080, '
        'https://testnet.com, '
        'wss://127.0.0.1.com, '
        'ttt://127.0.0.1.com, '
        'foo://127.0.0.1.com, '
        'NEK//127.0.0.1.com, '
    )

    formatted_text = HidingFormatter(
        BaseFormatter(), HIDING_PATTERNS
    ).format(text)

    assert formatted_text == '76c61fdfafba6ac36c308cebb724f92fadc76903c0cabd50ffaaef11790965e6, d76f6b3c67e29fe272385fb159c1065a1d09cc1912eebb0cd66de09fb6422cd5 172d42cb6f6f8b4d3d650dc79be219f7705a8a90fce358edc87c4d81fd40d053 c2265157597d6f471b23723cf04e3669312b1858c1ad65643edafda509cc3054 e557de85863fd2b97c0a0e3366d1e702b7ab186c563ac6b42c91d622916351fb ttt://127.0.0.1.com, foo://127.0.0.1.com, NEK//127.0.0.1.com, '  # noqa
