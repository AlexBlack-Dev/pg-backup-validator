# pg-backup-validator

Nightly proof that your PostgreSQL backups **actually restore**.

The most common DBA failure is not "no backup" — it's "backup exists but doesn't restore". This tool closes that gap: every night it takes the latest dump, restores it into a **clean ephemeral PostgreSQL container**, runs consistency checks (`SELECT COUNT(*)` on key tables, custom SQL), destroys the container and sends a report to Telegram/Slack.

Stack: **Python · Docker SDK · psycopg 3 · pydantic · pg_restore/psql from the postgres image itself**.

> Lab / pet project in the open. It demonstrates backup-automation skills; it is not a claim of production DBA tenure.

## How it works

```
./backups (or S3) ──> find latest dump ──> start postgres:16-alpine (ephemeral)
                                              mount ./backups:/backups:ro
                        ┌── pg_restore / psql *inside* the container
                        ▼
                     run checks ──> JSON + Markdown report ──> Telegram/Slack
                        └── destroy container (always, even on failure)
```

Supported formats: `.sql`, `.sql.gz`, `.dump` / `.custom` (pg_restore), WAL/PITR is out of scope for v0.1 (see Roadmap).

## Quickstart (local folder, 5 min)

```bash
pip install -e .
cp examples/validator.example.yaml validator.yaml
cp .env.example .env   # optional, env PGBV_* overrides yaml

# put a backup into ./backups, then:
pg-backup-validator -c validator.yaml list-backups
pg-backup-validator -c validator.yaml check-config
pg-backup-validator -c validator.yaml validate
```

Exit codes: `0` = restore + all checks OK, `2` = restore or checks failed, `1` = misconfiguration.

## Full demo with Docker (end-to-end, no real data needed)

```bash
docker compose -f docker/docker-compose.demo.yml up -d
# Windows:
scripts\make_demo_backup.bat
# Linux/macOS:
bash scripts/make_demo_backup.sh

pg-backup-validator -c examples/validator.example.yaml validate --no-notify
```

What happens: `source-db` is seeded from `scripts/demo_seed.sql` (`users`, `orders`), dumped with `pg_dump -Fc`, then the validator restores that dump into a throwaway container and checks `users >= 1`.

## Configuration

YAML + env. Priority: CLI/env `PGBV_*` > YAML > defaults.

| Key | Default | Meaning |
|---|---|---|
| `backup_dir` | `./backups` | where dumps live |
| `backup_patterns` | `*.dump, *.custom, *.sql, *.sql.gz` | glob list, newest by mtime wins |
| `postgres_image` | `postgres:16-alpine` | image for the ephemeral container |
| `expected_tables` | `{}` | `{table: min_rows}`, e.g. `{users: 1}` |
| `custom_checks` | `[]` | `{name, sql, min_value}` — scalar SQL must return `>= min_value` |
| `cleanup` / `keep_container_on_failure` | `true` / `false` | set keep=`true` to debug a failed restore |
| `telegram_enabled`, `telegram_token`, `telegram_chat_id` | off | Bot API via stdlib, no extra deps |
| `slack_enabled`, `slack_webhook_url` | off | incoming webhook |
| `s3_enabled`, `s3_bucket`, `s3_prefix` | off | needs `pip install .[s3]`, downloads newest object first |

See `examples/validator.example.yaml` and `examples/crontab.example` (nightly cron at 03:30).

## Example report

```
✅ pg-backup-validator — OK
Backup: `demo-20260101-033000.dump` (48210 bytes, custom)
Restore: 2.4s | Checks: 4 passed, 0 failed
- ✓ connectivity: SELECT 1 ok
- ✓ database_size: 8126464 bytes
- ✓ table:users: COUNT(*)=3, min=1
- ✓ table:orders: COUNT(*)=3, min=0
```

JSON goes to `./reports/validation-<ts>.json` (+ `latest.json` / `latest.md`).

## Project layout

```
src/pg_backup_validator/
  config.py         env + YAML settings (pydantic-settings)
  backup_source.py  local discovery + S3 download, kind detection
  docker_manager.py ephemeral postgres (context manager, always cleanup)
  restore.py        pg_restore/psql via `docker exec` inside the image
  checks.py         connectivity, db size, table counts, custom SQL
  report.py         JSON/Markdown/messenger rendering
  notify.py         Telegram + Slack via stdlib urllib
  main.py           orchestration  cli.py  argparse entrypoint
tests/              pytest, no docker/postgres needed (fakes/mocks)
docker/             Dockerfile.validator + demo compose
scripts/            demo seed + backup helpers
examples/           validator.yaml, crontab, .env
```

## Roadmap

- [ ] WAL-archive / PITR validation (`pgBackRest`, recovery to a timestamp)
- [ ] `pg_checksums` + `amcheck` corruption checks
- [ ] Prometheus metrics / OpenTelemetry spans per run
- [ ] Retention + S3 upload of validated reports

## License

MIT — see `LICENSE`.
