from pg_backup_validator.checks import CheckResult
from pg_backup_validator.report import ValidationReport


def test_markdown_ok():
    r = ValidationReport(started_at="2026-01-01T00:00:00+00:00", success=True, backup_name="a.dump", backup_size_bytes=10, backup_kind="custom", restore_sec=1.2, checks=[CheckResult("connectivity", True, "ok")])
    md = r.to_markdown()
    assert "OK" in md and "a.dump" in md


def test_messenger_failed_lists_failures_only():
    r = ValidationReport(started_at="x", success=False, backup_name="b.sql", checks=[CheckResult("connectivity", True, "ok"), CheckResult("table:users", False, "missing")], error="boom")
    text = r.to_messenger_text()
    assert "FAILED" in text
    assert "table:users" in text
