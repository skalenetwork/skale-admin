#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2021 SKALE Labs
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

import filecmp
import logging
import os
import shutil
import time
import threading
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, TypeVar

from core.schains.config.directory import get_files_with_prefix
from tools.configs.schains import SCHAINS_DIR_PATH
from tools.helper import read_json, write_json

IConfigFilenameType = TypeVar('IConfigFilenameType', bound='IConfigFilename')

logger = logging.getLogger(__name__)


class IConfigFilename(metaclass=ABCMeta):
    @property
    @abstractmethod
    def filename(self) -> str:
        pass

    def abspath(self, base_path: str) -> str:
        return os.path.join(base_path, self.filename)

    @classmethod
    @abstractmethod
    def from_filename(cls, filename: str) -> IConfigFilenameType:
        pass


class UpstreamConfigFilename(IConfigFilename):
    def __init__(self, name: str, rotation_id: int, ts: int) -> None:
        self.name = name
        self.rotation_id = rotation_id
        self.ts = ts

    @property
    def filename(self) -> str:
        return f'schain_{self.name}_{self.rotation_id}_{self.ts}.json'

    def __eq__(self, other) -> bool:
        return self.name == other.name and \
            self.rotation_id == other.rotation_id and \
            self.ts == other.ts

    def __lt__(self, other) -> bool:
        if self.name != other.name:
            return self.name < other.name
        elif self.rotation_id != other.rotation_id:
            return self.rotation_id < other.rotation_id
        else:
            return self.ts < other.ts

    @classmethod
    def from_filename(cls, filename: str):
        stem = Path(filename).stem
        ts_start = stem.rfind('_', 0, len(stem))
        ts: int = int(stem[ts_start + 1:])
        rid_start = stem.rfind('_', 0, ts_start)
        rotation_id: int = int(stem[rid_start + 1: ts_start])
        name = stem[:rid_start].replace('schain_', '', 1)
        return cls(name=name, rotation_id=rotation_id, ts=ts)


class SkaledConfigFilename(IConfigFilename):
    def __init__(self, name: str) -> None:
        self.name = name

    @property
    def filename(self) -> str:
        return f'schain_{self.name}.json'

    @classmethod
    def from_filename(cls, filename: str):
        _, name = filename.split('_')
        return cls(name)


class ConfigFileManager:
    CFM_LOCK = threading.Lock()

    def __init__(self, schain_name: str) -> None:
        self.schain_name: str = schain_name
        self.dirname: str = os.path.join(SCHAINS_DIR_PATH, schain_name)
        self.upstream_prefix = f'schain_{schain_name}_'

    def get_upstream_configs(self) -> List[UpstreamConfigFilename]:
        with ConfigFileManager.CFM_LOCK:
            filenames = get_files_with_prefix(
                self.dirname,
                self.upstream_prefix
            )
        return sorted(list(map(UpstreamConfigFilename.from_filename, filenames)))

    @property
    def latest_upstream_path(self) -> Optional[str]:
        upstreams = self.get_upstream_configs()
        if len(upstreams) == 0:
            return None
        return upstreams[-1].abspath(self.dirname)

    @property
    def tmp_path(self) -> str:
        return os.path.join(
            self.dirname,
            f'tmp_schain_{self.schain_name}.json'
        )

    @property
    def skaled_config_path(self) -> str:
        return SkaledConfigFilename(self.schain_name).abspath(self.dirname)

    def upstream_config_exists(self) -> bool:
        path = self.latest_upstream_path
        return path is not None and os.path.isfile(path)

    def skaled_config_exists(self) -> bool:
        path = SkaledConfigFilename(self.schain_name).abspath(self.dirname)
        return os.path.isfile(path)

    @property
    def latest_upstream_config(self) -> Optional[Dict]:
        if not self.upstream_config_exists():
            return None
        return read_json(self.latest_upstream_path)

    @property
    def skaled_config(self):
        if not self.skaled_config_exists():
            return None
        return read_json(self.skaled_config_path)

    def skaled_config_synced_with_upstream(self) -> bool:
        if not self.skaled_config_exists():
            return False
        if not self.upstream_config_exists():
            return True
        upstream_path = self.latest_upstream_path or ''
        with ConfigFileManager.CFM_LOCK:
            return filecmp.cmp(
                upstream_path,
                self.skaled_config_path
            )

    def get_new_upstream_filepath(self, rotation_id: int) -> str:
        ts = int(time.time())
        filename = UpstreamConfigFilename(
            self.schain_name,
            rotation_id=rotation_id,
            ts=ts
        )
        return filename.abspath(self.dirname)

    def save_new_upstream(self, rotation_id: int, config: Dict) -> None:
        tmp_path = self.tmp_path
        write_json(tmp_path, config)
        config_filepath = self.get_new_upstream_filepath(rotation_id)
        with ConfigFileManager.CFM_LOCK:
            shutil.move(tmp_path, config_filepath)

    def save_skaled_config(self, config: Dict) -> None:
        tmp_path = self.tmp_path
        write_json(tmp_path, config)
        with ConfigFileManager.CFM_LOCK:
            shutil.move(tmp_path, self.skaled_config_path)

    def sync_skaled_config_with_upstream(self) -> bool:
        if not self.upstream_config_exists():
            return False
        upath = self.latest_upstream_path or ''
        path = self.skaled_config_path
        logger.debug('Syncing %s with %s', path, upath)
        with ConfigFileManager.CFM_LOCK:
            shutil.copy(upath, path)
        return True

    def upstreams_by_rotation_id(self, rotation_id: int) -> List[str]:
        return [
            fp.abspath(self.dirname)
            for fp in self.get_upstream_configs()
            if fp.rotation_id == rotation_id
        ]

    def upstream_exist_for_rotation_id(self, rotation_id: int) -> bool:
        return len(self.upstreams_by_rotation_id(rotation_id)) > 0

    def remove_skaled_config(self) -> None:
        with ConfigFileManager.CFM_LOCK:
            os.remove(self.skaled_config_path)
