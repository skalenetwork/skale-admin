import os
from time import sleep
from http import HTTPStatus

from collections import namedtuple
from multiprocessing import Process

import mock
import docker
import pytest

from core.schains.skaled_exit_codes import SkaledExitCodes
from core.schains.checks import MissingExpectedConfigError, SChainChecks, CheckRes
from core.schains.runner import get_container_info
from core.schains.config.directory import get_schain_check_filepath

from tools.configs.containers import SCHAIN_CONTAINER
from tools.helper import read_json

from web.models.schain import upsert_schain_record, SChainRecord

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


class SChainChecksMock(SChainChecks):
    @property
    def firewall_rules(self) -> CheckRes:
        return CheckRes(True)


@pytest.fixture
def sample_false_checks(schain_config, schain_db, rule_controller, dutils):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    return SChainChecks(
        NOT_EXISTS_SCHAIN_NAME,
        TEST_NODE_ID,
        schain_record=schain_record,
        needed_config=schain_config,
        rule_controller=rule_controller,
        dutils=dutils
    )


@pytest.fixture
def rules_unsynced_checks(
    schain_config,
    uninited_rule_controller,
    schain_db,
    dutils
):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    return SChainChecks(
        schain_name,
        TEST_NODE_ID,
        schain_record=schain_record,
        needed_config=schain_config,
        rule_controller=uninited_rule_controller,
        dutils=dutils
    )


def test_data_dir_check(schain_checks, sample_false_checks):
    assert schain_checks.config_dir.status
    assert not sample_false_checks.config_dir.status


def test_dkg_check(schain_checks, sample_false_checks):
    assert schain_checks.dkg.status
    assert not sample_false_checks.dkg.status


def test_config_check(schain_checks, schain_config):
    r = schain_checks.config
    assert r.msg == 'ok'
    assert r.status
    nconfig = schain_checks.needed_config
    nconfig['skaleConfig']['sChain']['nodes'][0]['publicIp'] = '127.0.0.3'
    r = schain_checks.config
    assert r.msg == 'outdated'
    assert not r.status


def test_config_check_no_file(sample_false_checks):
    r = sample_false_checks.config
    assert not r.status
    assert r.msg == 'no file'


def test_config_check_wrong_version(schain_checks):
    schain_checks.schain_record = SchainRecordMock('9.8.7')
    schain_checks.needed_config['version'] = '9.9.8'
    r = schain_checks.config
    assert not r.status
    assert r.msg == 'version discrepancy'


def test_volume_check(schain_checks, sample_false_checks, dutils):
    dutils.cli.inspect_volume = lambda _: True
    assert schain_checks.volume.status
    dutils.cli.inspect_volume = mock.Mock(
        side_effect=docker.errors.NotFound('')
    )
    assert not sample_false_checks.volume.status


def test_firewall_rules_check(schain_checks, rules_unsynced_checks):
    schain_checks.rc.sync()
    assert schain_checks.firewall_rules.status
    assert not rules_unsynced_checks.firewall_rules.status


def test_container_check(schain_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert schain_checks.skaled_container.status
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_ERROR):
        assert not sample_false_checks.skaled_container.status


def test_exit_code_ok_check(schain_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code', return_value=0), \
            mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert schain_checks.exit_code_ok.status
    with mock.patch('core.schains.checks.DockerUtils.container_exit_code',
                    return_value=SkaledExitCodes.EC_STATE_ROOT_MISMATCH), \
            mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert not sample_false_checks.exit_code_ok.status


def test_ima_check(schain_checks, sample_false_checks):
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_OK):
        assert schain_checks.ima_container.status
    with mock.patch('core.schains.checks.DockerUtils.get_info', return_value=CONTAINER_INFO_ERROR):
        assert not sample_false_checks.ima_container.status


def test_rpc_check(schain_checks, schain_db):
    ok_result = response_mock(HTTPStatus.OK, {
        "id": 83,
        "jsonrpc": "2.0",
        "result": "0x4b7"
    })
    with mock.patch('requests.post', new=request_mock(ok_result)):
        assert schain_checks.rpc.status

    failed_attempts = 4
    none_result = response_mock(None)
    with mock.patch('requests.post', new=request_mock(none_result)):
        for _ in range(failed_attempts):
            assert not schain_checks.rpc.status

    err_result = response_mock(HTTPStatus.BAD_REQUEST, {})
    with mock.patch('requests.post', new=request_mock(err_result)):
        for _ in range(failed_attempts):
            assert not schain_checks.rpc.status

    rmock = request_mock(ok_result)
    schain_checks.schain_record.set_failed_rpc_count(3)
    expected_timeout = 60
    with mock.patch('requests.post', rmock):
        assert schain_checks.rpc.status
        assert rmock.call_args == mock.call(
            'http://0.0.0.0:10003',
            json={'jsonrpc': '2.0', 'method': 'eth_blockNumber', 'params': [], 'id': 1},
            cookies=None,
            timeout=expected_timeout
        )


def test_blocks_check(schain_checks):
    res_mock = response_mock(HTTPStatus.OK, ETH_GET_BLOCK_RESULT)
    with mock.patch('requests.post', return_value=res_mock):
        with mock.patch('time.time', return_value=TEST_TIMESTAMP):
            assert schain_checks.blocks.status
    with mock.patch('requests.post', return_value=res_mock):
        assert not schain_checks.blocks.status


def test_init_checks(skale, schain_db, uninited_rule_controller, dutils):
    schain_name = schain_db
    schain_record = SChainRecord.get_by_name(schain_name)
    checks = SChainChecks(
        schain_name,
        TEST_NODE_ID,
        schain_record=schain_record,
        rule_controller=uninited_rule_controller,
        dutils=dutils
    )
    assert checks.name == schain_name
    assert checks.node_id == TEST_NODE_ID


def test_exit_code(skale, rule_controller, schain_db, dutils):
    test_schain_name = schain_db
    image_name, container_name, _, _ = get_container_info(
        SCHAIN_CONTAINER, test_schain_name)

    schain_record = SChainRecord.get_by_name(test_schain_name)
    dutils.safe_rm(container_name)
    try:
        dutils.run_container(
            image_name=image_name,
            name=container_name,
            entrypoint='bash -c "exit 200"'
        )
        sleep(10)
        checks = SChainChecks(
            test_schain_name,
            TEST_NODE_ID,
            schain_record=schain_record,
            rule_controller=rule_controller,
            dutils=dutils
        )
        assert not checks.exit_code_ok.status
    except Exception as e:
        dutils.safe_rm(container_name)
        raise e
    dutils.safe_rm(container_name)


def test_process(skale, rule_controller, schain_db, dutils):
    schain_record = SChainRecord.get_by_name(schain_db)
    checks = SChainChecks(
        schain_db,
        TEST_NODE_ID,
        schain_record=schain_record,
        rule_controller=rule_controller,
        dutils=dutils
    )
    assert not checks.process.status

    process = Process(target=sleep, args=(5,))
    process.start()
    schain_record.set_monitor_id(process.ident)
    assert checks.process.status
    process.join()
    assert not checks.process.status


def test_get_all(schain_config, rule_controller, dutils, schain_db):
    schain_name = schain_config['skaleConfig']['sChain']['schainName']
    schain_record = SChainRecord.get_by_name(schain_name)
    node_id = schain_config['skaleConfig']['sChain']['nodes'][0]['nodeID']
    checks = SChainChecksMock(
        schain_db,
        node_id,
        schain_record=schain_record,
        needed_config=schain_config,
        rule_controller=rule_controller,
        dutils=dutils
    )
    checks_dict = checks.get_all()

    assert isinstance(checks_dict['config_dir'], bool)
    assert isinstance(checks_dict['dkg'], bool)
    assert isinstance(checks_dict['config'], bool)
    assert isinstance(checks_dict['firewall_rules'], bool)
    assert isinstance(checks_dict['skaled_container'], bool)
    assert isinstance(checks_dict['exit_code_ok'], bool)
    assert isinstance(checks_dict['rpc'], bool)
    assert isinstance(checks_dict['blocks'], bool)
    assert isinstance(checks_dict['ima_container'], bool)
    assert isinstance(checks_dict['process'], bool)

    checks_without_ima = SChainChecksMock(
        schain_db,
        node_id,
        schain_record=schain_record,
        needed_config=schain_config,
        rule_controller=rule_controller,
        dutils=dutils,
        ima_linked=False
    )
    checks_dict_without_ima = checks_without_ima.get_all()
    assert 'ima_container' not in checks_dict_without_ima

    filtered_checks = checks_without_ima.get_all(checks_filter=['config', 'volume'])
    assert len(filtered_checks) == 2

    filtered_checks = checks_without_ima.get_all(checks_filter=['ima_container'])
    assert len(filtered_checks) == 0

    filtered_checks = checks_without_ima.get_all(checks_filter=['<0_0>'])
    assert len(filtered_checks) == 0


def test_get_all_with_save(
    node_config,
    schain_config,
    rule_controller,
    dutils,
    schain_db
):
    name = schain_db
    record = SChainRecord.get_by_name(name)
    checks = SChainChecksMock(
        schain_db,
        TEST_NODE_ID,
        schain_record=record,
        needed_config=schain_config,
        rule_controller=rule_controller,
        dutils=dutils
    )
    schain_check_path = get_schain_check_filepath(schain_db)
    assert not os.path.isfile(schain_check_path)
    schain_checks = checks.get_all(save=True)
    assert os.path.isfile(schain_check_path)
    checks_from_file = read_json(schain_check_path)
    assert schain_checks == checks_from_file['checks']


def test_config_check_wtihout_needed_config(
    skale,
    node_config,
    rule_controller,
    schain_db,
    dutils
):
    name = schain_db
    record = upsert_schain_record(name)
    checks = SChainChecks(
        name,
        TEST_NODE_ID,
        schain_record=record,
        rule_controller=rule_controller,
        dutils=dutils
    )
    with pytest.raises(MissingExpectedConfigError):
        checks.config
    with pytest.raises(MissingExpectedConfigError):
        checks.get_all()
