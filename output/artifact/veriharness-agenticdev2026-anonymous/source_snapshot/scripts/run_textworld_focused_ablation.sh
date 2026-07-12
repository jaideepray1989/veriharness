#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python_bin=".venv/bin/python"
config="configs/experiment_textworld_focused_ablation_budget_4.yaml"
models_config="configs/models.yaml"
model="local_ollama_qwen_coder_14b"
experiment_id="textworld_focused_ablation_budget_4"
run_dir="runs/${experiment_id}_${model}"
compiled_dir="runs/${experiment_id}_compiled_qwen_coder_14b"

if [[ -d "$run_dir" ]]; then
  "$python_bin" -m veriharness.cli.main resume-run --run-dir "$run_dir"
else
  "$python_bin" -m veriharness.cli.main run-model-matrix \
    --config "$config" \
    --models-config "$models_config" \
    --models "$model" \
    --backend local \
    --skip-unavailable
fi

"$python_bin" -m veriharness.cli.main aggregate --run-dir "$run_dir"
"$python_bin" -m veriharness.cli.main compile-workshop \
  --run-dirs "$run_dir" \
  --out-dir "$compiled_dir" \
  --expected-rows 200
