#!/bin/bash
set -euo pipefail

cd /Users/jaray/Documents/autoresearch
mkdir -p runs
exec .venv/bin/python scripts/run_reviewer_extension.py >> runs/reviewer_extension.log 2>&1
