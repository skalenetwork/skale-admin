import io
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import mock

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from core.firewall.base.nftables import NFTablesCmdFailedError
from core.firewall.tls import open_tls_ports
from core.monitor.fair.action_skaled import FairSkaledActionManager
from tools.constants.fair import SKALED_RESTART_JOB_NAME
from web.helper import get_api_url
from web.routes import ssl


def test_restart_keeps_earliest_deadline():
    scheduler = BackgroundScheduler()
    scheduler.start(paused=True)
    record = SimpleNamespace(restart_ts=0)
    record.set_restart_ts = lambda ts: setattr(record, 'restart_ts', ts)
    manager = SimpleNamespace(
        scheduler=scheduler, chain_record=record, recreated_skaled_container=lambda: None
    )
    schedule = FairSkaledActionManager.schedule_skaled_restart.__wrapped__
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        with (
            mock.patch('core.monitor.fair.action_skaled.time.time', return_value=now),
            mock.patch(
                'core.monitor.fair.action_skaled.random_timestamp_between',
                side_effect=lambda start, end: end,
            ),
        ):
            assert schedule(manager, now + 3900)
            assert record.restart_ts == now + 3600
            assert not schedule(manager, now + 4000)
            assert schedule(manager, now + 900)
            assert record.restart_ts == now + 600
            assert not schedule(manager, now + 900)
            assert schedule(manager, now - 10)
            assert record.restart_ts == now
            jobs = scheduler.get_jobs()
            assert len(jobs) == 1
            assert jobs[0].id == SKALED_RESTART_JOB_NAME
            assert jobs[0].next_run_time.timestamp() == now
    finally:
        scheduler.shutdown()


def test_restart_record_is_preserved_when_scheduling_fails():
    manager = SimpleNamespace(
        scheduler=mock.Mock(), chain_record=mock.Mock(), recreated_skaled_container=mock.Mock()
    )
    manager.scheduler.get_job.return_value = None
    manager.scheduler.add_job.side_effect = RuntimeError('scheduler unavailable')
    with pytest.raises(RuntimeError, match='scheduler unavailable'):
        FairSkaledActionManager.schedule_skaled_restart.__wrapped__(manager, 0)
    assert manager.chain_record.set_restart_ts.call_args == mock.call(
        manager.chain_record.restart_ts
    )


def test_tls_ports_are_saved_and_retries_are_idempotent(tmp_path):
    path = tmp_path / 'tls-ports.conf'
    path.write_text('set skale_tls_ports { type inet_service; }\n')
    with (
        mock.patch('core.firewall.tls.NFT_CHAIN_BASE_PATH', tmp_path),
        mock.patch('core.firewall.tls.NFTablesController') as controller,
    ):
        controller.return_value.run_cmd.return_value = (0, '', '')
        open_tls_ports()
        saved = path.read_text()
        assert 'elements = { 311, 443 }' in saved
        open_tls_ports()
        assert path.read_text() == saved
        controller.return_value.run_cmd.return_value = (1, '', 'set missing')
        with pytest.raises(NFTablesCmdFailedError, match='set missing'):
            open_tls_ports()
        assert path.read_text() == saved


@pytest.mark.parametrize('nginx_ok,firewall_error', [(True, False), (False, False), (True, True)])
def test_ssl_upload_updates_firewall_after_nginx(tmp_path, nginx_ok, firewall_error):
    app = Flask(__name__)
    app.register_blueprint(ssl.ssl_bp)
    events = []

    def reload_nginx():
        assert (tmp_path / 'ssl_cert').read_bytes() == b'certificate'
        events.append('nginx')
        return nginx_ok

    def open_ports():
        events.append('firewall')
        if firewall_error:
            raise OSError('firewall unavailable')

    with (
        mock.patch.object(ssl, 'SSL_CERTIFICATES_FILEPATH', tmp_path),
        mock.patch.object(ssl, 'is_ssl_folder_empty', return_value=True),
        mock.patch.object(ssl, 'get_cert_info', return_value=('ok', {})),
        mock.patch.object(ssl, 'set_schains_need_reload'),
        mock.patch.object(ssl, 'reload_node_proxy', side_effect=reload_nginx),
        mock.patch.object(ssl, 'open_tls_ports', side_effect=open_ports),
    ):
        response = (
            app.test_client()
            .post(
                get_api_url('ssl', 'upload'),
                data={
                    'json': '{}',
                    'ssl_cert': (io.BytesIO(b'certificate'), 'cert'),
                    'ssl_key': (io.BytesIO(b'key'), 'key'),
                },
            )
            .get_json()
        )
    assert events == (['nginx', 'firewall'] if nginx_ok else ['nginx'])
    if not nginx_ok:
        assert response == {'status': 'error', 'payload': ssl.CERTS_NOT_SERVED}
    elif firewall_error:
        assert response == {'status': 'error', 'payload': ssl.CERTS_FIREWALL_ERROR}
    else:
        assert response == {'status': 'ok', 'payload': {}}
