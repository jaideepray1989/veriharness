#!/bin/bash
set -euo pipefail

MODEL_KEY="$1"
cd /Users/jaray/Documents/autoresearch
mkdir -p runs
.venv/bin/python scripts/run_modal_paper900.py --model-key "$MODEL_KEY" \
  >> "runs/modal_paper900_${MODEL_KEY}.log" 2>&1
launchctl remove "org.veriharness.modal-paper900-${MODEL_KEY}" 2>/dev/null || true
