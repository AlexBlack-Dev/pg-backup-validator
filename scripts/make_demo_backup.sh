#!/usr/bin/env bash
set -euo pipefail
mkdir -p backups
TS=$(date +%Y%m%d-%H%M%S)
docker exec pgbv-demo-source pg_dump -U demo -d demo -Fc -f /tmp/demo.dump
docker cp pgbv-demo-source:/tmp/demo.dump "backups/demo-${TS}.dump"
echo "Backup saved to backups/demo-${TS}.dump"
