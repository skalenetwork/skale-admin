#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026-Present SKALE Labs
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.

import hashlib
import ipaddress
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, StrictUndefined, Template

from core.chain.ssl import is_ssl_on
from core.config.endpoint import get_chain_ports_from_config, get_internal_chain_ports
from core.firewall import IpRange
from core.nginx.params import get_nginx_params, resolve_exempt_hosts
from tools.constants import (
    NGINX_BASE_TEMPLATE_FILEPATH,
    NGINX_CHAIN_TEMPLATE_FILEPATH,
    SSL_CERT_PATH,
)

CLIENT_ZONE_SIZE = '8m'
LOOPBACK = '127.0.0.1'
# loopback-only location in each chain file that answers with the file's fingerprint
PROBE_PATH = '/.skale-proxy'


def chain_ident(chain_name: str) -> str:
    """nginx variable and zone names allow letters, digits and underscores only"""
    return re.sub(r'[^A-Za-z0-9_]', '_', chain_name)


def ips_to_cidrs(ips: Iterable[str]) -> list[str]:
    return [f'{ip}/32' for ip in ips]


def ranges_to_cidrs(ranges: Iterable[IpRange]) -> list[str]:
    cidrs = []
    for ip_range in ranges:
        start = ipaddress.IPv4Address(ip_range.start_ip)
        end = ipaddress.IPv4Address(ip_range.end_ip)
        cidrs.extend(str(net) for net in ipaddress.summarize_address_range(start, end))
    return cidrs


def render_fingerprinted(template: Template, data: dict, salt: bytes = b'') -> str:
    """Renders with a fingerprint of the rest of the text and the salt"""
    draft = template.render(data, fingerprint='')
    fingerprint = hashlib.sha256(draft.encode() + salt).hexdigest()[:16]
    return template.render(data, fingerprint=fingerprint)


def render_base_config(
    ssl_on: bool, skale_node: bool, template_path: Path = NGINX_BASE_TEMPLATE_FILEPATH
) -> str:
    """base.conf fingerprinted with its certificate, byte-identical to node-cli's render"""
    template = Environment().from_string(template_path.read_text())
    cert = SSL_CERT_PATH.read_bytes() if ssl_on and SSL_CERT_PATH.is_file() else b''
    return render_fingerprinted(template, {'ssl': ssl_on, 'skale_node': skale_node}, cert)


@dataclass
class ChainProxyConfig:
    chain_name: str
    ports: dict
    peers: list[str]
    exempt_ips: list[str]
    ssl: bool
    njs: bool
    limits: dict

    def template_data(self) -> dict:
        peers = sorted({ipaddress.IPv4Network(cidr, strict=False) for cidr in self.peers})
        # an exempt address inside a peer network would lose its peer rights to the longer prefix
        exempt_ips = sorted(
            {
                ip
                for ip in (LOOPBACK, *self.exempt_ips)
                if not any(ipaddress.IPv4Address(ip) in net for net in peers)
            }
        )
        internal = get_internal_chain_ports(self.ports)
        return {
            'chain': self.chain_name,
            'id': chain_ident(self.chain_name),
            'http_port': self.ports['http'],
            'ws_port': self.ports['ws'],
            'https_port': self.ports['https'],
            'wss_port': self.ports['wss'],
            'http_internal': internal['http'],
            'ws_internal': internal['ws'],
            'peers': [str(net) for net in peers],
            'exempt_ips': exempt_ips,
            'ssl': self.ssl,
            'njs': self.njs,
            'limits': self.limits,
            'client_zone_size': CLIENT_ZONE_SIZE,
            'probe_path': PROBE_PATH,
            # unddos per-minute budgets, as the sustained zone allows them over one minute
            'client_rpm': self.limits['per_client_sustained_rps'] * 60
            + self.limits['sustained_burst'],
            'global_rpm': self.limits['global_rps'] * 60,
        }

    def render(self, template_path: Path = NGINX_CHAIN_TEMPLATE_FILEPATH) -> str:
        env = Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
        )
        return render_fingerprinted(
            env.from_string(template_path.read_text()), self.template_data()
        )


def build_chain_proxy_config(
    chain_name: str, skaled_config: dict, peers: list[str]
) -> ChainProxyConfig:
    params = get_nginx_params()
    return ChainProxyConfig(
        chain_name=chain_name,
        ports=get_chain_ports_from_config(skaled_config),
        peers=peers,
        exempt_ips=resolve_exempt_hosts(params.get('exempt_hosts', [])),
        ssl=is_ssl_on(),
        njs=bool(params.get('njs', False)),
        limits=params['limits'],
    )
