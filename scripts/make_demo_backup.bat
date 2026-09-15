@echo off
REM Make a demo backup from the demo source DB into .\backups\
if not exist backups mkdir backups
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TS=%%i
docker exec pgbv-demo-source pg_dump -U demo -d demo -Fc -f /tmp/demo.dump
docker cp pgbv-demo-source:/tmp/demo.dump backups\demo-%TS%.dump
echo Backup saved to backups\demo-%TS%.dump
