import mock
import pytest
from time import sleep
from http import HTTPStatus

from collections import namedtuple

from core.schains.skaled_exit_codes import SkaledExitCodes

from core.schains.checks import SChainChecks
from core.schains.runner import get_container_info
from tools.configs.containers import SCHAIN_CONTAINER


from tests.utils import response_mock, request_mock


NOT_EXISTS_SCHAIN_NAME = 'qwerty123'
SCHAIN_CONTAINER_NAME = 'skale_schain_test'
TEST_NODE_ID = 0
REMOVING_CONTAINER_WAITING_INTERVAL = 2

CONTAINER_INFO_OK = {'status': 'running'}
CONTAINER_INFO_ERROR = {'status': 'exited'}

TEST_TIMESTAMP_HEX = '0x55ba467c'
TEST_TIMESTAMP = int(TEST_TIMESTAMP_HEX, 16)

ETH_GET_BLOCK_RESULT = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "difficulty": "0x4ea3f27bc",
        "extraData": "0x476574682f4c5649562f76312e302e302f6c696e75782f676f312e342e32",
        "gasLimit": "0x1388",
        "gasUsed": "0x0",
        "hash": "0xdc0818cf78f21a8e70579cb46a43643f78291264dda342ae31049421c82d21ae",
        "logsBloom": "0x0",
        "miner": "0xbb7b8287f3f0a933474a79eae42cbca977791171",
        "mixHash": "0x4fffe9ae21f1c9e15207b1f472d5bbdd68c9595d461666602f2be20daf5e7843",
        "nonce": "0x689056015818adbe",
        "number": "0x1b4",
        "parentHash": "0xe99e022112df268087ea7eafaf4790497fd21dbeeb6bd7a1721df161a6657a54",
        "receiptsRoot": "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421",
        "sha3Uncles": "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347",
        "size": "0x220",
        "stateRoot": "0xddc8b0234c2e0cad087c8b389aa7ef01f7d79b2570bccb77ce48648aa61c904d",
        "timestamp": TEST_TIMESTAMP_HEX,
        "totalDifficulty": "0x78ed983323d",
        "transactions": [
        ],
        "transactionsRoot": "0x56e81f171bcc55a6ff8345e692c0f86e5b48e01b996cadc001622fb5e363b421"
    }
}

SchainRecordMock = namedtuple('SchainRecord', ['config_version'])


@pytest.fixture
def sample_checks(schain_config):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    return SChainChecks(schain_name, node_id)


@pytest.fixture
def sample_false_checks():
    return SChainChecks(NOT_EXISTS_SCHAIN_NAME, TEST_NODE_ID)


def test_data_dir_check(sample_checks, sample_false_checks):
    assert sample_checks.data_dir
    assert not sample_false_checks.data_dir


def test_dkg_check(sample_checks, sample_false_checks):
    assert sample_checks.dkg
    assert not sample_false_checks.dkg


def test_config_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        assert sample_checks.config
        assert not sample_false_checks.config


def test_config_check_wrong_version(sample_checks, sample_false_checks):
    schain_record_mock = SchainRecordMock('9.8.7')
    with mock.patch('core.schains.config.generator.upsert_schain_record',
                    return_value=schain_record_mock):
        assert not sample_checks.config


def test_volume_check(sample_checks, sample_false_checks):
    with mock.patch('docker.api.client.APIClient.inspect_volume',
                    new=mock.Mock(return_value=True)):
        assert sample_checks.volume
    assert not sample_false_checks.volume


def test_firewall_rules_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.apsent_iptables_rules', return_value=[]), \
            mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        assert sample_checks.firewall_rules
    with mock.patch('core.schains.checks.apsent_iptables_rules',
                    return_value=[('1.1.1.1', 1000)]), \
            mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        assert not sample_false_checks.firewall_rules


def test_container_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert sample_checks.container
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_ERROR):
        assert not sample_false_checks.container


def test_exit_code_ok_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code', return_value=0), \
            mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert sample_checks.exit_code_ok
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code',
                    return_value=SkaledExitCodes.EC_STATE_ROOT_MISMATCH), \
            mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert not sample_false_checks.exit_code_ok


def test_ima_check(sample_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert sample_checks.ima_container
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_ERROR):
        assert not sample_false_checks.ima_container


def test_rpc_check(sample_checks, sample_false_checks):
    res_mock = response_mock(HTTPStatus.OK, {
        "id": 83,
        "jsonrpc": "2.0",
        "result": "0x4b7"
    })
    with mock.patch('requests.post', new=request_mock(res_mock)), \
            mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        assert sample_checks.rpc
    with mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        assert not sample_false_checks.rpc


def test_blocks_check(sample_checks, sample_false_checks):
    res_mock = response_mock(HTTPStatus.OK, ETH_GET_BLOCK_RESULT)
    with mock.patch('core.schains.checks.schain_config_version_match', return_value=True):
        with mock.patch('requests.post', return_value=res_mock), \
                mock.patch('time.time', return_value=TEST_TIMESTAMP):
            assert sample_checks.blocks
        with mock.patch('requests.post', return_value=res_mock):
            assert not sample_false_checks.blocks


def test_init_checks(skale):
    schain_name = 'name'
    checks = SChainChecks(schain_name, TEST_NODE_ID)
    assert checks.name == schain_name
    assert checks.node_id == TEST_NODE_ID


def test_exit_code(skale, dutils):
    test_schain_name = 'exit_code_ok_test'
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, test_schain_name)
    dutils.safe_rm(container_name)
    try:
        dutils.run_container(
            image_name=image_name,
            name=container_name,
            entrypoint='bash -c "exit 200"'
        )
        sleep(10)
        checks = SChainChecks(test_schain_name, TEST_NODE_ID, dutils=dutils)
        assert not checks.exit_code_ok
    except Exception as e:
        dutils.safe_rm(container_name)
        raise e
    dutils.safe_rm(container_name)
