from pathlib import Path

from filelock import FileLock

from core.firewall.base.nftables import NFTablesCmdFailedError, NFTablesController
from tools.constants import NFT_CHAIN_BASE_PATH


def open_tls_ports() -> None:
    """Open node TLS services in the set provisioned by node-cli and persist it."""
    path = Path(NFT_CHAIN_BASE_PATH) / 'tls-ports.conf'
    with FileLock(path.with_suffix('.lock'), timeout=120):
        controller = NFTablesController(chain='tls')
        rc, _, error = controller.run_cmd('add element inet firewall skale_tls_ports { 311, 443 }')
        if rc != 0:
            raise NFTablesCmdFailedError(f'Failed to open TLS ports: {error}')
        temporary = path.with_suffix('.tmp')
        temporary.write_text(
            'set skale_tls_ports { type inet_service; elements = { 311, 443 }; }\n'
        )
        temporary.replace(path)
