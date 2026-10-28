from unittest import mock

import pytest

from core.firewall.base.nftables import NFTablesCmdFailedError
from core.firewall.tls import open_tls_ports


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
