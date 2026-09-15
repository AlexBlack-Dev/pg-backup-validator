from pg_backup_validator.backup_source import detect_kind, find_backups, find_latest


def test_detect_kind():
    assert detect_kind("a.sql") == "sql"
    assert detect_kind("A.SQL.GZ") == "sql.gz"
    assert detect_kind("nightly.dump") == "custom"
    assert detect_kind("x.custom") == "custom"
    assert detect_kind("x.bak") == "custom"
    assert detect_kind("x.txt") == "unknown"


def test_find_latest_orders_by_mtime(tmp_path):
    (tmp_path / "old.sql").write_text("select 1")
    (tmp_path / "new.sql").write_text("select 2")
    import os, time
    old = tmp_path / "old.sql"
    new = tmp_path / "new.sql"
    now = time.time()
    os.utime(old, (now - 100, now - 100))
    os.utime(new, (now, now))
    latest = find_latest(tmp_path, ["*.sql"])
    assert latest is not None
    assert latest.name == "new.sql"
    assert latest.kind == "sql"


def test_find_backups_empty(tmp_path):
    assert find_backups(tmp_path, ["*.dump"]) == []
    assert find_latest(tmp_path, ["*.dump"]) is None
