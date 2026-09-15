"""Validation report: JSON + Markdown + short messenger text."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from pg_backup_validator.checks import CheckResult


@dataclass
class ValidationReport:
    started_at: str
    success: bool
    backup_name: str = ""
    backup_size_bytes: int = 0
    backup_kind: str = ""
    restore_sec: float = 0.0
    checks: List[CheckResult] = field(default_factory=list)
    error: str = ""
    host: str = ""

    @property
    def passed(self) -> int:
        return sum(1 for c in self.checks if c.ok)

    @property
    def failed(self) -> int:
        return sum(1 for c in self.checks if not c.ok)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def to_markdown(self) -> str:
        icon = "✅" if self.success else "❌"
        lines = [
            f"{icon} **pg-backup-validator** — {'OK' if self.success else 'FAILED'}",
            f"Backup: `{self.backup_name}` ({self.backup_size_bytes} bytes, {self.backup_kind})",
            f"Restore: {self.restore_sec:.1f}s | Checks: {self.passed} passed, {self.failed} failed",
        ]
        if self.error:
            lines.append(f"Error: `{self.error}`")
        for c in self.checks:
            mark = "✓" if c.ok else "✗"
            lines.append(f"- {mark} {c.name}: {c.detail}")
        return "\n".join(lines)

    def to_messenger_text(self) -> str:
        status = "OK ✅" if self.success else "FAILED ❌"
        lines = [
            f"pg-backup-validator: {status}",
            f"Backup: {self.backup_name} ({self.backup_size_bytes} B, {self.backup_kind})",
            f"Restore: {self.restore_sec:.1f}s, checks {self.passed}/{len(self.checks)} passed",
        ]
        if self.error:
            lines.append(f"Error: {self.error[:500]}")
        for c in self.checks:
            if not c.ok:
                lines.append(f"FAIL {c.name}: {c.detail[:200]}")
        return "\n".join(lines)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_report(report: ValidationReport, report_dir: str | Path) -> Path:
    d = Path(report_dir)
    d.mkdir(parents=True, exist_ok=True)
    stamp = report.started_at.replace(":", "-").replace("+", "plus")
    out = d / f"validation-{stamp}.json"
    out.write_text(report.to_json(), encoding="utf-8")
    (d / "latest.json").write_text(report.to_json(), encoding="utf-8")
    (d / "latest.md").write_text(report.to_markdown(), encoding="utf-8")
    return out
