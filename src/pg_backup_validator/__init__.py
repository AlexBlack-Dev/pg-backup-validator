"""pg-backup-validator: nightly proof that your PostgreSQL backups actually restore."""

from pg_backup_validator.report import ValidationReport, CheckResult

__all__ = ["ValidationReport", "CheckResult"]
__version__ = "0.1.0"
