"""Checks tested with a fake DB-API connection (no postgres needed)."""

from pg_backup_validator.checks import check_custom_sql, check_table_count, run_checks


class FakeCursor:
    def __init__(self, counts, custom_value=7):
        self.counts = counts
        self.custom_value = custom_value
        self.last_sql = ""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql):
        self.last_sql = sql
        if "pg_database_size" in sql:
            self._row = (12345,)
        elif sql.strip().startswith("SELECT COUNT"):
            self._row = (self._current_count,)
        else:
            self._row = (self.custom_value,)

    def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self, counts=None, custom_value=7, fail_on=None):
        self.counts = counts or {}
        self.custom_value = custom_value
        self.fail_on = fail_on or set()

    def cursor(self):
        cur = FakeCursor(self.counts, self.custom_value)
        orig_execute = cur.execute

        def execute(sql):
            for marker in self.fail_on:
                if marker in sql:
                    raise RuntimeError(f"relation {marker} does not exist")
            for table, count in self.counts.items():
                if table in sql:
                    cur._current_count = count
                    break
            else:
                cur._current_count = 0
            return orig_execute(sql)
        cur.execute = execute
        return cur


def test_table_count_pass_and_fail():
    conn = FakeConn(counts={"users": 5})
    ok = check_table_count(conn, "users", 1)
    assert ok.ok and ok.value == 5
    bad = check_table_count(conn, "users", 10)
    assert not bad.ok


def test_missing_table_is_failure():
    conn = FakeConn(counts={}, fail_on={"missing"})
    res = check_table_count(conn, "missing", 0)
    assert not res.ok


def test_custom_sql_min_value():
    conn = FakeConn(counts={"orders": 7})
    ok = check_custom_sql(conn, "orders_today", "SELECT COUNT(*) FROM orders", min_value=5)
    assert ok.ok
    bad = check_custom_sql(conn, "orders_today", "SELECT COUNT(*) FROM orders", min_value=50)
    assert not bad.ok


def test_run_checks_counts():
    conn = FakeConn(counts={"users": 3, "orders": 3})
    class C:
        name = "big_orders"
        sql = "SELECT COUNT(*) FROM orders"
        min_value = 2
    results = run_checks(conn, {"users": 1}, [C()])
    assert len(results) >= 4
    assert all(r.ok for r in results)
