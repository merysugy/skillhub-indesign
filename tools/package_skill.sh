#!/usr/bin/env bash
# Builds dist/indesign-layout-prep.zip, ready to upload to claude.ai
# (Settings > Capabilities > Skills > Upload skill).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
rm -f dist/indesign-layout-prep.zip
cd skills
zip -rq ../dist/indesign-layout-prep.zip indesign-layout-prep \
  -x '*.DS_Store' -x '*__pycache__*' -x '*.pyc'
cd ..
echo "Built dist/indesign-layout-prep.zip"
unzip -l dist/indesign-layout-prep.zip | tail -n +4 | sed '$d' | sed '$d'
