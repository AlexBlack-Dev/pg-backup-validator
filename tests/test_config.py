from pg_backup_validator.config import load_settings


def test_load_from_yaml(tmp_path):
    cfg = tmp_path / "v.yaml"
    cfg.write_text("backup_dir: ./backups\npostgres_db: demo\nexpected_tables:\n  users: 1\n  orders: 0\n", encoding="utf-8")
    s = load_settings(cfg)
    assert s.postgres_db == "demo"
    assert s.expected_tables == {"users": 1, "orders": 0}


def test_env_overrides_yaml(tmp_path, monkeypatch):
    cfg = tmp_path / "v.yaml"
    cfg.write_text("postgres_db: from_file\n", encoding="utf-8")
    monkeypatch.setenv("PGBV_POSTGRES_DB", "from_env")
    s = load_settings(cfg)
    assert s.postgres_db == "from_env"
