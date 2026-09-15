"""Backup discovery: local directory (+ optional S3)."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class BackupInfo:
    path: Path
    size_bytes: int
    mtime: float
    kind: str  # 'sql' | 'sql.gz' | 'custom' | 'unknown'

    @property
    def name(self) -> str:
        return self.path.name


def detect_kind(path: str | Path) -> str:
    name = str(path).lower()
    if name.endswith(".sql.gz"):
        return "sql.gz"
    if name.endswith(".sql"):
        return "sql"
    if name.endswith(".dump") or name.endswith(".custom") or name.endswith(".bak"):
        return "custom"
    return "unknown"


def find_backups(backup_dir: str | Path, patterns: List[str]) -> List[BackupInfo]:
    d = Path(backup_dir)
    if not d.is_dir():
        return []
    found: dict[str, Path] = {}
    for pat in patterns:
        for p in d.glob(pat):
            if p.is_file():
                found[str(p.resolve())] = p
    infos = []
    for p in found.values():
        st = p.stat()
        infos.append(
            BackupInfo(
                path=p,
                size_bytes=st.st_size,
                mtime=st.st_mtime,
                kind=detect_kind(p),
            )
        )
    infos.sort(key=lambda b: b.mtime, reverse=True)
    return infos


def find_latest(backup_dir: str | Path, patterns: List[str]) -> Optional[BackupInfo]:
    backups = find_backups(backup_dir, patterns)
    return backups[0] if backups else None


def assert_usable(backup: BackupInfo, min_size_bytes: int = 1) -> None:
    if backup.size_bytes < min_size_bytes:
        raise ValueError(f"Backup {backup.path} is empty ({backup.size_bytes} bytes)")
    if backup.kind == "unknown":
        raise ValueError(
            f"Backup {backup.path} has unknown format. "
            "Use .sql, .sql.gz, .dump or .custom"
        )


def format_age(mtime: float, now: Optional[float] = None) -> str:
    now = now if now is not None else time.time()
    age = max(0, int(now - mtime))
    h, rem = divmod(age, 3600)
    m, s = divmod(rem, 60)
    if h >= 24:
        return f"{h // 24}d {h % 24}h ago"
    if h:
        return f"{h}h {m}m ago"
    if m:
        return f"{m}m ago"
    return f"{s}s ago"


def download_latest_from_s3(
    bucket: str,
    prefix: str,
    dest_dir: str | Path,
    endpoint_url: str = "",
    region: str = "eu-central-1",
) -> BackupInfo:
    """Download newest object from S3 into dest_dir. Requires extra `s3` (boto3)."""
    try:
        import boto3  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("S3 support needs `pip install pg-backup-validator[s3]`") from e

    client_kwargs: dict = {}
    if endpoint_url:
        client_kwargs["endpoint_url"] = endpoint_url
    s3 = boto3.client("s3", **client_kwargs) if client_kwargs else boto3.client(
        "s3", region_name=region
    )
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    objects = resp.get("Contents", [])
    if not objects:
        raise FileNotFoundError(f"No objects in s3://{bucket}/{prefix}")
    objects.sort(key=lambda o: o["LastModified"], reverse=True)
    key = objects[0]["Key"]
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    local_path = dest / Path(key).name
    s3.download_file(bucket, key, str(local_path))
    st = local_path.stat()
    return BackupInfo(
        path=local_path, size_bytes=st.st_size, mtime=st.st_mtime, kind=detect_kind(local_path)
    )


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).lower() in ("1", "true", "yes", "on")
