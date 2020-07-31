import mock
import pytest
from core.tg_bot import TgBot
from tests.schains.checks_test import SChainChecks, NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID

TG_SEND_MSG_RES = {
    'message_id': 1,
    'date': 1590069709,
    'text': 'test'
}


@pytest.fixture
def bot():
    return TgBot('123', '123')


class Bot:
    def __init__(self, api_key):
        pass

    def send_message(self, text, chat_id):
        return {
            'message_id': 1,
            'date': 1590069709,
            'text': text
        }


def test_send_message():
    with mock.patch('core.tg_bot.Bot', new=Bot):
        bot = TgBot('123', '123')
        res = bot.send_message('test')
    assert res == TG_SEND_MSG_RES


def test_send_failed_dkg_notification():
    with mock.patch('core.tg_bot.Bot', new=Bot):
        bot = TgBot('123', '123')
        res = bot.send_failed_dkg_notification('test_schain')
        assert res['text'] == '\u2757 DKG failedsChain name: test_schain'


def test_send_schain_checks():
    with mock.patch('core.tg_bot.Bot', new=Bot):
        bot = TgBot('123', '123')

    checks = SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID)
    res = bot.send_schain_checks(checks)

    assert 'Data directory: \u274C\nDKG: \u274C\nConfig: \u274C\nVolume: \u274C\nContainer: \u274C\nFirewall: \u274C\nRPC: \u274C\n' in res['text'] # noqa
    assert '\u2757 Checks failed \n\nNode ID: 0\nsChain name: qwerty123\n' in res['text']
