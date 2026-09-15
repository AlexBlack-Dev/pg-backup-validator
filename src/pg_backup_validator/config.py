"""Configuration: env-vars (PGBV_*) + optional YAML file.

Priority: explicit kwargs > env-vars > YAML file > defaults.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CustomCheck(BaseSettings):
    name: str = ""
    sql: str = ""
    min_value: Optional[int] = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PGBV_", extra="ignore")

    # --- backup source ---
    backup_dir: Path = Field(default=Path("./backups"))
    backup_patterns: List[str] = Field(
        default=["*.dump", "*.custom", "*.sql", "*.sql.gz", "*.bak"]
    )
    # S3 (optional, requires extra `s3`)
    s3_enabled: bool = False
    s3_bucket: str = ""
    s3_prefix: str = ""
    s3_endpoint_url: str = ""
    s3_region: str = "eu-central-1"

    # --- ephemeral postgres ---
    postgres_image: str = "postgres:16-alpine"
    postgres_user: str = "validator"
    postgres_password: str = "validator_secret"
    postgres_db: str = "restore_check"
    # 0 = let Docker pick a random host port
    host_port: int = 0
    container_prefix: str = "pgbv"
    ready_timeout_sec: int = 60
    restore_timeout_sec: int = 600
    keep_container_on_failure: bool = False

    # --- checks ---
    # {"users": 1, "orders": 0}  -> table must exist, COUNT(*) >= min rows
    expected_tables: Dict[str, int] = Field(default_factory=dict)
    custom_checks: List[CustomCheck] = Field(default_factory=list)

    # --- notifications ---
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    slack_enabled: bool = False
    slack_webhook_url: str = ""

    # --- reporting ---
    report_dir: Path = Field(default=Path("./reports"))
    cleanup: bool = True

    @field_validator("backup_patterns", mode="before")
    @classmethod
    def _split_patterns(cls, v: Any) -> Any:
        # allow PGBV_BACKUP_PATTERNS="*.dump,*.sql"
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return v


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config {p} must contain a YAML mapping at top level")
    return data


def load_settings(config_path: str | Path | None = None, **overrides: Any) -> Settings:
    """Build Settings from YAML file + env-vars + explicit overrides.

    Priority: explicit kwargs > PGBV_* env-vars > YAML file > defaults.
    NOTE: pydantic-settings gives init-kwargs priority over env, so we must
    drop YAML keys that are also set via env, otherwise YAML would win.
    """
    import os

    data: Dict[str, Any] = {}
    if config_path:
        data.update(load_yaml(config_path))
    # env wins over file: drop file keys shadowed by PGBV_* env vars
    for field_name in Settings.model_fields:
        if os.getenv(f"PGBV_{field_name.upper()}") is not None:
            data.pop(field_name, None)
    # explicit kwargs win over everything
    data.update({k: v for k, v in overrides.items() if v is not None})
    return Settings(**data)
