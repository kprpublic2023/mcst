#!/usr/bin/env bash
# 정기 수집 cron 예시.
# crontab -e 후 (매일 03:00 KST):
#   0 3 * * * /path/to/mcst/scripts/schedule.sh >> /path/to/mcst/data/cron.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
python -m mcst.cli collect
python -m mcst.cli report --out reports/output --pdf || true
