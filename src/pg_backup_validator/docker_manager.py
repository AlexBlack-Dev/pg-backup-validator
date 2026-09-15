"""Ephemeral PostgreSQL in Docker: start clean, wait ready, always cleanup."""

from __future__ import annotations

import socket
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Optional


@dataclass
class ConnParams:
    host: str
    port: int
    user: str
    password: str
    dbname: str

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} "
            f"user={self.user} password={self.password} dbname={self.dbname}"
        )


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class EphemeralPostgres:
    """Context manager: `with EphemeralPostgres(...) as pg:` gives live ConnParams.

    Mounts `backup_dir` read-only into the container at /backups so restore
    commands can reference /backups/<filename> without copying data.
    """

    def __init__(
        self,
        image: str,
        user: str,
        password: str,
        dbname: str,
        backup_dir: str | Path,
        container_prefix: str = "pgbv",
        host_port: int = 0,
        ready_timeout_sec: int = 60,
    ) -> None:
        self.image = image
        self.user = user
        self.password = password
        self.dbname = dbname
        self.backup_dir = Path(backup_dir).resolve()
        self.container_prefix = container_prefix
        self.host_port = host_port or find_free_port()
        self.ready_timeout_sec = ready_timeout_sec
        self.container = None
        self.container_name = f"{container_prefix}-{uuid.uuid4().hex[:8]}"

    def start(self) -> ConnParams:
        try:
            import docker  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("Docker support needs `pip install docker`") from e
        try:
            client = docker.from_env()
            client.images.pull(self.image)
            self.container = client.containers.run(
                self.image,
                name=self.container_name,
                detach=True,
                auto_remove=False,
                environment={
                    "POSTGRES_USER": self.user,
                    "POSTGRES_PASSWORD": self.password,
                    "POSTGRES_DB": self.dbname,
                },
                ports={"5432/tcp": ("127.0.0.1", self.host_port)},
                volumes={str(self.backup_dir): {"bind": "/backups", "mode": "ro"}},
                command=["postgres", "-c", "log_min_messages=WARNING"],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to start ephemeral postgres: {e}") from e
        conn = ConnParams(
            host="127.0.0.1",
            port=self.host_port,
            user=self.user,
            password=self.password,
            dbname=self.dbname,
        )
        self.wait_ready(conn, timeout_sec=self.ready_timeout_sec)
        return conn

    def wait_ready(self, conn: ConnParams, timeout_sec: int = 60) -> None:
        import psycopg  # type: ignore
        deadline = time.time() + timeout_sec
        last_err: Optional[Exception] = None
        while time.time() < deadline:
            try:
                with psycopg.connect(
                    host=conn.host,
                    port=conn.port,
                    user=conn.user,
                    password=conn.password,
                    dbname=conn.dbname,
                    connect_timeout=3,
                ) as c:
                    with c.cursor() as cur:
                        cur.execute("SELECT 1")
                        cur.fetchone()
                return
            except Exception as e:
                last_err = e
                time.sleep(1.0)
        raise TimeoutError(
            f"Postgres {self.container_name} not ready in {timeout_sec}s: {last_err}"
        )

    def stop(self) -> None:
        if self.container is None:
            return
        try:
            self.container.stop(timeout=10)
        except Exception:
            pass
        try:
            self.container.remove(force=True)
        except Exception:
            pass
        self.container = None

    def __enter__(self) -> ConnParams:
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
