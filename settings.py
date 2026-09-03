"""Validated standalone backend settings loaded only from the local environment."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)


class ConnectionEnvironment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    DYNAMODB_REGION: str = Field(min_length=1)
    THIS_ENV: str = Field(min_length=1)
    ES_HOST_DEFAULT: str = Field(min_length=1)
    ES_PORT_DEFAULT: int | None = Field(default=None, ge=1, le=65535)
    ES_USERNAME_DEFAULT: str = Field(min_length=1)
    ES_PASSWORD_DEFAULT: SecretStr
    ACCESS_KEY: SecretStr
    SECRET_KEY: SecretStr


class DashboardSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    environment: ConnectionEnvironment

    @property
    def elasticsearch_url(self) -> str:
        host = self.environment.ES_HOST_DEFAULT.rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        port = self.environment.ES_PORT_DEFAULT
        return host if port is None else f"{host}:{port}"


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "CHANGE_ME" in value or "YOUR_" in value:
        raise RuntimeError(f"{name} is not configured")
    return value


@lru_cache(maxsize=1)
def load_settings() -> DashboardSettings:
    raw_port = os.getenv("ES_PORT_DEFAULT", "").strip()
    return DashboardSettings(
        environment=ConnectionEnvironment(
            DYNAMODB_REGION=_required("DYNAMODB_REGION"),
            THIS_ENV=_required("THIS_ENV"),
            ES_HOST_DEFAULT=_required("ES_HOST_DEFAULT"),
            ES_PORT_DEFAULT=int(raw_port) if raw_port else None,
            ES_USERNAME_DEFAULT=_required("ES_USERNAME_DEFAULT"),
            ES_PASSWORD_DEFAULT=SecretStr(_required("ES_PASSWORD_DEFAULT")),
            ACCESS_KEY=SecretStr(_required("ACCESS_KEY")),
            SECRET_KEY=SecretStr(_required("SECRET_KEY")),
        )
    )
