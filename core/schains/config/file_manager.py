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

import os
from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import List, TypeVar

from tools.configs.schains import SCHAINS_DIR_PATH
from core.schains.config.directory import get_files_with_prefix

IConfigFilenameType = TypeVar('IConfigFilenameType', bound='IConfigFilename')


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
        rstem = Path(filename).stem[::-1]
        ts_, rotation_id_, prefix_name = rstem.split('_', maxsplit=2)
        name = prefix_name[::-1].replace('schain_', '', 1)
        rotation_id: int = int(rotation_id_)
        ts: int = int(ts_)
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
    def __init__(self, schain_name: str) -> None:
        self.schain_name: str = schain_name
        self.dirname: str = os.path.join(SCHAINS_DIR_PATH, schain_name)
        self.upstream_prefix = f'schain_{schain_name}_'

    def get_upstream_configs(self) -> List[IConfigFilename]:
        filenames = get_files_with_prefix(self.dirname, self.upstream_prefix)
        return sorted(list(map(lambda f: UpstreamConfigFilename.from_filename(f), filenames)))

    @property
    def latest_upstream_path(self) -> str:
        filename = self.get_upstream_configs()[-1]
        return filename.abspath(self.dirname)

    @property
    def skaled_config_path(self) -> str:
        return SkaledConfigFilename(self.schain_name).abspath(self.dirname)
