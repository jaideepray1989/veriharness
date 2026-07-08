# Official Runner Bridge

Date: 2026-07-08

Purpose: make VeriHarness outputs consumable by official external benchmark runners, so external numbers can be produced from preserved leaf traces rather than ad hoc manual copy/paste.

## Bridge Commands Added

| Command | Purpose |
|---|---|
| `export-swebench-predictions` | Convert VeriHarness SWE-bench leaf artifacts into official SWE-bench prediction JSONL. |
| `run-swebench-official` | Print or execute `swebench.harness.run_evaluation` with the exported predictions. |
| `export-mlagentbench-manifests` | Export VeriHarness MLAgentBench `research_plan.json` artifacts and an index. |
| `run-mlagentbench-official` | Print or execute MLAgentBench `prepare_task`, `runner`, and `eval` commands; optionally writes a JSON plan and shell script. |

Implementation:

- `/Users/jaray/Documents/autoresearch/veriharness/experiments/official_runners.py`
- `/Users/jaray/Documents/autoresearch/veriharness/cli/main.py`
- `/Users/jaray/Documents/autoresearch/tests/test_official_runner_bridge.py`

## Smoke Evidence

Source VeriHarness run:

- `/Users/jaray/Documents/autoresearch/runs/external_benchmarks_smoke`

Generated artifacts:

| Artifact | Meaning |
|---|---|
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/swebench_lite_H4_predictions.jsonl` | Official SWE-bench JSONL prediction file, 1 row. |
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/swebench_official_dry_run.json` | Exact official SWE-bench command, dry-run mode. |
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/mlagentbench_H4_manifests/manifest_index.json` | Exported MLAgentBench manifest index, 1 row. |
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/mlagentbench_official_plan.json` | Official MLAgentBench prepare/runner/eval command plan. |
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/mlagentbench_official_plan.sh` | Executable shell script for the same MLAgentBench plan. |
| `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/mlagentbench_official_dry_run.json` | Exact MLAgentBench command plan, dry-run mode. |

Validation:

```bash
.venv/bin/python -m pytest tests/test_official_runner_bridge.py tests/test_external_benchmarks.py -q
.venv/bin/python -m ruff check veriharness/experiments/official_runners.py veriharness/cli/main.py tests/test_official_runner_bridge.py
```

Result:

- `8 passed`
- `All checks passed`
- The generated dry-run JSON files parse with `python -m json.tool`.

## SWE-bench Paper Workflow

Run VeriHarness patch generation:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_swebench_subset.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

Export one prediction file per policy and dataset:

```bash
.venv/bin/python -m veriharness.cli.main export-swebench-predictions \
  --run-dir <veriharness_run_dir> \
  --out official_runs/swebench/H4_lite_predictions.jsonl \
  --variant H4 \
  --benchmark swebench_lite \
  --model-name veriharness-H4-qwen-coder-14b
```

Run official SWE-bench in an evaluator environment with Docker and `swebench` installed:

```bash
.venv/bin/python -m veriharness.cli.main run-swebench-official \
  --predictions-path official_runs/swebench/H4_lite_predictions.jsonl \
  --dataset-name princeton-nlp/SWE-bench_Lite \
  --run-id veriharness_h4_lite_qwen14b \
  --python-bin <python_with_swebench> \
  --max-workers 4 \
  --report-dir official_runs/swebench/reports \
  --execute
```

The resulting SWE-bench report is the paper-facing number. VeriHarness local patch/reference checks should be reported only as adapter smoke, not as SWE-bench performance.

## MLAgentBench Paper Workflow

Export VeriHarness plans for auditing:

```bash
.venv/bin/python -m veriharness.cli.main export-mlagentbench-manifests \
  --run-dir <veriharness_run_dir> \
  --out-dir official_runs/mlagentbench/manifests/H4 \
  --variant H4
```

Generate an official MLAgentBench command plan:

```bash
.venv/bin/python -m veriharness.cli.main run-mlagentbench-official \
  --tasks cifar10,imdb \
  --python-bin <python_with_mlagentbench> \
  --task-python <task_python> \
  --log-root official_runs/mlagentbench/logs/H4 \
  --work-root official_runs/mlagentbench/workspace/H4 \
  --eval-root official_runs/mlagentbench/eval/H4 \
  --out-plan official_runs/mlagentbench/H4_plan.json \
  --execute
```

The bridge can run official MLAgentBench prepare/runner/eval commands and archive VeriHarness plan artifacts. To claim an official MLAgentBench score for a VeriHarness policy, the remaining paper-critical step is an MLAgentBench agent shim that consumes the VeriHarness plan or delegates actions through VeriHarness inside the upstream runner. Without that shim, MLAgentBench official numbers should be described as upstream-runner/baseline numbers plus VeriHarness manifest evidence, not as full H4 policy scores.

## Local Evaluator Status

This Mac environment is `arm64`, has no `docker` command on `PATH`, and the current `.venv` does not have `swebench` or `MLAgentBench` installed. Therefore this commit demonstrates bridge correctness with dry-run official commands and machine-readable artifacts, but does not claim completed official SWE-bench or MLAgentBench benchmark scores.
