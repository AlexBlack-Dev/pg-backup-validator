"""Consistency checks against the restored database."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    value: Optional[int] = None
    duration_ms: int = 0


def _timed(fn):
    started = time.time()
    try:
        result = fn()
        ms = int((time.time() - started) * 1000)
        if isinstance(result, CheckResult):
            result.duration_ms = ms
        return result
    except Exception as e:
        ms = int((time.time() - started) * 1000)
        return CheckResult(name=getattr(fn, "__name__", "check"), ok=False, detail=f"exception: {e}", duration_ms=ms)


def check_connectivity(conn) -> CheckResult:
    def _run() -> CheckResult:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return CheckResult(name="connectivity", ok=True, detail="SELECT 1 ok")
    _run.__name__ = "connectivity"
    return _timed(_run)


def check_database_size(conn) -> CheckResult:
    def _run() -> CheckResult:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_database_size(current_database())")
            row = cur.fetchone()
        size = int(row[0]) if row else 0
        return CheckResult(name="database_size", ok=size > 0, detail=f"{size} bytes", value=size)
    _run.__name__ = "database_size"
    return _timed(_run)


def check_table_count(conn, table: str, min_rows: int = 0) -> CheckResult:
    def _run() -> CheckResult:
        parts = [f'"{p.replace(chr(34), chr(34) * 2)}"' for p in table.split(".")]
        ident = ".".join(parts)
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {ident}")
            row = cur.fetchone()
        count = int(row[0]) if row else 0
        return CheckResult(name=f"table:{table}", ok=count >= min_rows, detail=f"COUNT(*)={count}, min={min_rows}", value=count)
    _run.__name__ = f"table:{table}"
    try:
        return _timed(_run)
    except Exception as e:
        return CheckResult(name=f"table:{table}", ok=False, detail=str(e))


def check_custom_sql(conn, name: str, sql: str, min_value: Optional[int] = None) -> CheckResult:
    started = time.time()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
        value = None
        try:
            value = int(row[0]) if row and row[0] is not None else None
        except (TypeError, ValueError):
            value = None
        if min_value is not None and value is not None:
            ok = value >= min_value
            detail = f"value={value}, min={min_value}"
        else:
            ok = True
            detail = f"value={value}" if value is not None else "query ok"
        return CheckResult(name=f"custom:{name}", ok=ok, detail=detail, value=value, duration_ms=int((time.time() - started) * 1000))
    except Exception as e:
        return CheckResult(name=f"custom:{name}", ok=False, detail=str(e), duration_ms=int((time.time() - started) * 1000))


def run_checks(conn, expected_tables: Dict[str, int], custom_checks: list) -> List[CheckResult]:
    results: List[CheckResult] = [check_connectivity(conn), check_database_size(conn)]
    for table, min_rows in (expected_tables or {}).items():
        results.append(check_table_count(conn, table, int(min_rows)))
    for c in custom_checks or []:
        name = getattr(c, "name", "sql") or "sql"
        sql = getattr(c, "sql", "") or ""
        min_value = getattr(c, "min_value", None)
        if sql.strip():
            results.append(check_custom_sql(conn, name, sql, min_value))
    return results


def summarize(results: List[CheckResult]) -> Dict[str, int]:
    return {"total": len(results), "passed": sum(1 for r in results if r.ok), "failed": sum(1 for r in results if not r.ok)}
