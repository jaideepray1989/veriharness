#!/bin/bash
set -euo pipefail

cd /Users/jaray/Documents/autoresearch
mkdir -p runs
exec .venv/bin/python scripts/run_paper900.py >> runs/paper900.log 2>&1
