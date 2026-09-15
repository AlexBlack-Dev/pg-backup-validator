from pg_backup_validator.restore import build_restore_command


def test_build_sql():
    cmd = build_restore_command("/backups/a.sql", "u", "db", "sql")
    assert "psql" in cmd and "/backups/a.sql" in cmd and "ON_ERROR_STOP" in cmd


def test_build_gz_uses_pipe():
    cmd = build_restore_command("/backups/a.sql.gz", "u", "db", "sql.gz")
    assert "gunzip" in cmd and "psql" in cmd


def test_build_custom_uses_pg_restore():
    cmd = build_restore_command("/backups/a.dump", "u", "db", "custom")
    assert "pg_restore" in cmd and "--clean" in cmd
