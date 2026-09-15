"""CLI: validate / list-backups / check-config."""

from __future__ import annotations

import argparse
import json
import sys

from pg_backup_validator import backup_source
from pg_backup_validator.config import load_settings


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pg-backup-validator", description="Restore the latest PG backup into ephemeral Docker PG and verify it.")
    p.add_argument("-c", "--config", default=None, help="Path to validator.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate", help="run one validation cycle")
    v.add_argument("--json", action="store_true", help="print JSON report to stdout")
    v.add_argument("--no-notify", action="store_true", help="skip Telegram/Slack")
    l = sub.add_parser("list-backups", help="show discovered backups, newest first")
    l.add_argument("--limit", type=int, default=10)
    sub.add_parser("check-config", help="print effective config and exit")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings(args.config)
    if args.cmd == "check-config":
        data = settings.model_dump(mode="json")
        for k in ("postgres_password", "telegram_token", "slack_webhook_url"):
            if data.get(k):
                data[k] = "***"
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
        return 0
    if args.cmd == "list-backups":
        backups = backup_source.find_backups(settings.backup_dir, settings.backup_patterns)
        if not backups:
            print(f"No backups in {settings.backup_dir}")
            return 1
        for b in backups[: args.limit]:
            age = backup_source.format_age(b.mtime)
            print(f"{b.name}  {b.size_bytes:>10} B  {b.kind:<7} {age}")
        return 0
    if args.cmd == "validate":
        if args.no_notify:
            settings.telegram_enabled = False
            settings.slack_enabled = False
        from pg_backup_validator.main import validate_and_report
        report = validate_and_report(settings)
        if args.json:
            print(report.to_json())
        else:
            print(report.to_markdown())
        return 0 if report.success else 2
    return 1


if __name__ == "__main__":
    import sys as _sys
    _sys.exit(main())
