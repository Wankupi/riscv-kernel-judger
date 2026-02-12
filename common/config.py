from __future__ import annotations
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class ConfigRedis(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0)
    password: str | None = None
    queue_key: str = "riscv-kernel-judger:queue"


class ConfigServer(BaseModel):
    upload_dir: Path = Path("./uploads")
    max_file_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class ConfigRunner(BaseModel):
    tftp_kernel_path: Path = Path("./static/boot/kernel.img")
    tty_power: str
    relay_addrs: list[int]
    default_timeout: int = Field(default=30, ge=1)


class ConfigBroadcast(BaseModel):
    tty_device: str
    baudrate: int = Field(default=115200, ge=1)
    tcp_port: int = Field(default=12345, ge=1, le=65535)


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore", env_nested_delimiter="_", yaml_file=["config.yaml", "config.yml"]
    )

    redis: ConfigRedis
    server: ConfigServer
    runner: ConfigRunner
    broadcast: ConfigBroadcast

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            YamlConfigSettingsSource(settings_cls),
            env_settings,
            dotenv_settings,
            init_settings,
            file_secret_settings,
        )


config: Config = Config()  # type: ignore
