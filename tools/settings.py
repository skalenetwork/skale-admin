#   -*- coding: utf-8 -*-
#
#   This file is part of SKALE Admin
#
#   Copyright (C) 2026 SKALE Labs
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

from functools import lru_cache
from pathlib import Path
from typing import TypeAlias

from pydantic import AnyUrl, BaseModel, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from core.types.settings import EnvType, NodeMode, NodeType
from tools.constants import (
    ADMIN_SETTINGS_PATH,
    NESTED_DELIMITER,
    NODE_DATA_FOLDER_NAME,
    NODE_SETTINGS_PATH,
)


class TomlBaseSettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


class SkaleContracts(BaseModel):
    manager: str
    ima: str


class FairContracts(BaseModel):
    fair: str


class BaseAdminSettings(TomlBaseSettings):
    env_type: EnvType
    skale_dir_host: Path
    endpoint: AnyUrl
    backup_run: bool = False
    pull_config_for_schain: str | None = None
    bite: bool = False

    @field_validator('skale_dir_host', mode='before')
    @classmethod
    def validate_skale_dir_host(cls, value: Path | str) -> Path:
        return Path(value).expanduser().resolve()

    @property
    def node_data_path_host(self) -> Path:
        return self.skale_dir_host / NODE_DATA_FOLDER_NAME

    model_config = SettingsConfigDict(
        toml_file=ADMIN_SETTINGS_PATH,
        env_nested_delimiter=NESTED_DELIMITER,
    )


class SkaleBaseSettings(BaseAdminSettings):
    contracts: SkaleContracts


class SkaleSettings(SkaleBaseSettings):
    sgx_url: AnyUrl


SkalePassiveSettings: TypeAlias = SkaleBaseSettings


class FairBaseSettings(BaseAdminSettings):
    contracts: FairContracts


class FairSettings(FairBaseSettings):
    sgx_url: AnyUrl


FairPassiveSettings: TypeAlias = FairBaseSettings


ActiveSettings: TypeAlias = SkaleSettings | FairSettings


class NodeSettings(TomlBaseSettings):
    node_type: NodeType
    node_mode: NodeMode

    model_config = SettingsConfigDict(toml_file=NODE_SETTINGS_PATH)


@lru_cache
def get_node_settings() -> NodeSettings:
    return NodeSettings()  # type: ignore[call-arg]


@lru_cache
def get_skale_settings() -> SkaleSettings:
    return SkaleSettings()  # type: ignore[call-arg]


@lru_cache
def get_skale_base_settings() -> SkaleBaseSettings | SkaleSettings:
    node_settings = get_node_settings()
    if node_settings.node_mode == 'passive':
        return SkaleBaseSettings()  # type: ignore[call-arg]
    return SkaleSettings()  # type: ignore[call-arg]


@lru_cache
def get_fair_settings() -> FairSettings:
    return FairSettings()  # type: ignore[call-arg]


@lru_cache
def get_fair_base_settings() -> FairBaseSettings:
    return FairBaseSettings()  # type: ignore[call-arg]


@lru_cache
def get_active_settings() -> ActiveSettings:
    node_settings = get_node_settings()
    if node_settings.node_mode == 'passive':
        raise ValueError('Active settings are not available for passive nodes')
    if node_settings.node_type == 'fair':
        return get_fair_settings()
    return get_skale_settings()


@lru_cache
def get_settings() -> SkaleSettings | SkaleBaseSettings | FairSettings | FairBaseSettings:
    node_settings = get_node_settings()
    if node_settings.node_type == 'fair':
        if node_settings.node_mode == 'passive':
            return get_fair_base_settings()
        return get_fair_settings()
    if node_settings.node_mode == 'passive':
        return get_skale_base_settings()
    return get_skale_settings()
