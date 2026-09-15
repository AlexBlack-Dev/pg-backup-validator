"""Orchestrator: find latest backup -> ephemeral PG -> restore -> checks -> report."""

from __future__ import annotations

import socket
from pathlib import Path

from pg_backup_validator import backup_source
from pg_backup_validator.checks import run_checks
from pg_backup_validator.config import Settings
from pg_backup_validator.docker_manager import EphemeralPostgres
from pg_backup_validator.notify import dispatch
from pg_backup_validator.report import ValidationReport, save_report, utcnow_iso
from pg_backup_validator.restore import run_restore


def validate_once(settings: Settings) -> ValidationReport:
    started_at = utcnow_iso()
    host = socket.gethostname()
    try:
        if settings.s3_enabled:
            backup = backup_source.download_latest_from_s3(bucket=settings.s3_bucket, prefix=settings.s3_prefix, dest_dir=settings.backup_dir, endpoint_url=settings.s3_endpoint_url, region=settings.s3_region)
        else:
            backup = backup_source.find_latest(settings.backup_dir, settings.backup_patterns)
    except Exception as e:
        return ValidationReport(started_at=started_at, success=False, host=host, error=f"source error: {e}")
    if backup is None:
        return ValidationReport(started_at=started_at, success=False, host=host, error=f"No backups in {settings.backup_dir} (patterns={settings.backup_patterns})")
    try:
        backup_source.assert_usable(backup)
    except Exception as e:
        return ValidationReport(started_at=started_at, success=False, host=host, backup_name=backup.name, backup_size_bytes=backup.size_bytes, backup_kind=backup.kind, error=str(e))
    pg = EphemeralPostgres(image=settings.postgres_image, user=settings.postgres_user, password=settings.postgres_password, dbname=settings.postgres_db, backup_dir=settings.backup_dir, container_prefix=settings.container_prefix, host_port=settings.host_port, ready_timeout_sec=settings.ready_timeout_sec)
    success = False
    restore_sec = 0.0
    try:
        try:
            conn_params = pg.start()
        except Exception as e:
            return ValidationReport(started_at=started_at, success=False, host=host, backup_name=backup.name, backup_size_bytes=backup.size_bytes, backup_kind=backup.kind, error=f"docker/start error: {e}")
        try:
            inside_path = f"/backups/{backup.path.name}"
            restored = run_restore(pg.container, inside_path, settings.postgres_user, settings.postgres_db, backup.kind, timeout_sec=settings.restore_timeout_sec)
            restore_sec = restored.duration_sec
            if not restored.ok:
                return ValidationReport(started_at=started_at, success=False, host=host, backup_name=backup.name, backup_size_bytes=backup.size_bytes, backup_kind=backup.kind, restore_sec=restore_sec, error=restored.error or restored.log_tail[-1000:])
            import psycopg  # type: ignore
            with psycopg.connect(host=conn_params.host, port=conn_params.port, user=conn_params.user, password=conn_params.password, dbname=conn_params.dbname, connect_timeout=10) as conn:
                results = run_checks(conn, settings.expected_tables, settings.custom_checks)
            success = all(r.ok for r in results)
            return ValidationReport(started_at=started_at, success=success, host=host, backup_name=backup.name, backup_size_bytes=backup.size_bytes, backup_kind=backup.kind, restore_sec=restore_sec, checks=results, error="" if success else "one or more checks failed")
        finally:
            if settings.cleanup and not (not success and settings.keep_container_on_failure):
                pg.stop()
    except Exception as e:
        try:
            pg.stop()
        except Exception:
            pass
        return ValidationReport(started_at=started_at, success=False, host=host, backup_name=backup.name, backup_size_bytes=backup.size_bytes, backup_kind=backup.kind, restore_sec=restore_sec, error=str(e)[:2000])


def validate_and_report(settings: Settings) -> ValidationReport:
    report = validate_once(settings)
    try:
        Path(settings.report_dir).mkdir(parents=True, exist_ok=True)
        save_report(report, settings.report_dir)
    except Exception:
        pass
    try:
        dispatch(report, settings)
    except Exception:
        pass
    return report
