"""Restore a dump *inside* the ephemeral container.

We deliberately run pg_restore/psql from the postgres image itself via
`docker exec`, so the cron host needs no postgres client binaries.
The backup dir is mounted at /backups (see docker_manager).
"""

from __future__ import annotations

import shlex
import time
from dataclasses import dataclass


@dataclass
class RestoreResult:
    ok: bool
    duration_sec: float
    command: str
    log_tail: str = ""
    error: str = ""


def build_restore_command(backup_inside_path: str, user: str, dbname: str, kind: str) -> str:
    """Return a shell command to run *inside* the container."""
    q = shlex.quote(backup_inside_path)
    u = shlex.quote(user)
    d = shlex.quote(dbname)
    if kind == "sql":
        return f"psql -U {u} -d {d} -v ON_ERROR_STOP=1 -f {q}"
    if kind == "sql.gz":
        return f"gunzip -c {q} | psql -U {u} -d {d} -v ON_ERROR_STOP=1"
    if kind in ("custom", "unknown"):
        return f"pg_restore -U {u} -d {d} --clean --if-exists --no-owner {q}"
    raise ValueError(f"Unsupported backup kind: {kind}")


def run_restore(container, backup_inside_path: str, user: str, dbname: str, kind: str, timeout_sec: int = 600) -> RestoreResult:
    cmd = build_restore_command(backup_inside_path, user, dbname, kind)
    started = time.time()
    try:
        rc, out = container.exec_run(["sh", "-c", cmd], demux=False)
        duration = time.time() - started
        text = _decode(out)
        tail = "\n".join(text.splitlines()[-40:])
        if rc == 0:
            return RestoreResult(ok=True, duration_sec=duration, command=cmd, log_tail=tail)
        return RestoreResult(ok=False, duration_sec=duration, command=cmd, log_tail=tail, error=f"restore exited with code {rc}")
    except Exception as e:
        return RestoreResult(ok=False, duration_sec=time.time() - started, command=cmd, error=str(e))


def _pgpassword(container) -> str:
    for e in container.attrs.get("Config", {}).get("Env", []):
        if e.startswith("POSTGRES_PASSWORD="):
            return e.split("=", 1)[1]
    return ""


def _decode(out) -> str:
    if out is None:
        return ""
    if isinstance(out, (bytes, bytearray)):
        return bytes(out).decode("utf-8", errors="replace")
    if isinstance(out, tuple):
        return "\n".join(_decode(x) for x in out if x)
    return str(out)
