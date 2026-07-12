#!/bin/bash
set -euo pipefail

cd <REPOSITORY_ROOT>
mkdir -p runs
exec .venv/bin/python scripts/run_reviewer_extension.py >> runs/reviewer_extension.log 2>&1
