#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python_bin=".venv/bin/python"
config="configs/experiment_typed_repair_cross_benchmark_budget_4.yaml"
models_config="configs/models.yaml"
experiment_id="typed_repair_cross_benchmark_budget_4"
models=(local_ollama_qwen_coder_14b local_ollama_qwen coreai_freeform)

for model in "${models[@]}"; do
  run_dir="runs/${experiment_id}_${model}"
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
done

"$python_bin" -m veriharness.cli.main compile-typed-repair-evidence \
  --run-dirs "runs/${experiment_id}_local_ollama_qwen_coder_14b,runs/${experiment_id}_local_ollama_qwen,runs/${experiment_id}_coreai_freeform" \
  --out reports/cross_benchmark_typed_repair_evidence.md \
  --expected-rows-per-model 1992
