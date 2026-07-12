# External Benchmark Integration

Date: 2026-07-07

Purpose: add paper-relevant external benchmarks that can test whether VeriHarness improvements generalize beyond the synthetic and public-NLP matrix.

## Benchmarks Added

| Benchmark | VeriHarness name | Source | Local oracle scope | Paper-quality scoring |
|---|---|---|---|---|
| SWE-bench Lite | `swebench_lite` | `princeton-nlp/SWE-bench_Lite` on Hugging Face | Reference-patch smoke check plus patch artifact gates | Official SWE-bench container evaluation |
| SWE-bench Verified | `swebench_verified` | `princeton-nlp/SWE-bench_Verified` on Hugging Face | Reference-patch smoke check plus patch artifact gates | Official SWE-bench container evaluation |
| DS-1000 | `ds1000` | `xlangai/DS-1000` on Hugging Face | Executable `test_execution(solution)` subprocess | Same executable oracle; report dependency failures separately |
| MLAgentBench | `mlagentbench` | `snap-stanford/MLAgentBench` GitHub repo | Manifest-shape oracle for train/eval plan | Upstream `MLAgentBench.runner` and `MLAgentBench.eval` |

## Code Paths

New benchmark loader:

- `/Users/jaray/Documents/autoresearch/veriharness/benchmarks/external_benchmarks.py`

Updated shared dispatch:

- `/Users/jaray/Documents/autoresearch/veriharness/benchmarks/generators.py`
- `/Users/jaray/Documents/autoresearch/veriharness/benchmarks/oracles.py`
- `/Users/jaray/Documents/autoresearch/veriharness/core/context_pack.py`
- `/Users/jaray/Documents/autoresearch/veriharness/leaves/prompts.py`
- `/Users/jaray/Documents/autoresearch/veriharness/llm/dummy_client.py`

Focused tests:

- `/Users/jaray/Documents/autoresearch/tests/test_external_benchmarks.py`

## Configs Added

| Config | Purpose | Rows |
|---|---|---:|
| `/Users/jaray/Documents/autoresearch/configs/experiment_external_benchmarks_smoke.yaml` | Dummy-client adapter smoke across SWE-bench Lite, DS-1000, and MLAgentBench | 6 |
| `/Users/jaray/Documents/autoresearch/configs/experiment_swebench_subset.yaml` | SWE-bench Lite/Verified subset | 200 |
| `/Users/jaray/Documents/autoresearch/configs/experiment_ds1000_subset.yaml` | DS-1000 executable repair probe | 400 |
| `/Users/jaray/Documents/autoresearch/configs/experiment_mlagentbench_subset.yaml` | MLAgentBench manifest adapter probe | 52 |

## Completed Smoke Run

Command:

```bash
.venv/bin/python -m veriharness.cli.main run \
  --config configs/experiment_external_benchmarks_smoke.yaml \
  --backend local
```

Run:

- `/Users/jaray/Documents/autoresearch/runs/external_benchmarks_smoke`

Committed compact data:

- `/Users/jaray/Documents/autoresearch/reports/data/external_benchmarks_smoke/results.jsonl`
- `/Users/jaray/Documents/autoresearch/reports/data/external_benchmarks_smoke/aggregate.json`
- `/Users/jaray/Documents/autoresearch/reports/data/external_benchmarks_smoke/leaderboard.csv`

Smoke results:

| Benchmark | Variant | Success | Artifact |
|---|---|---:|---|
| SWE-bench Lite | gated-resample | pass | `patch.diff` |
| SWE-bench Lite | typed-repair+retain | pass | `patch.diff` |
| DS-1000 | gated-resample | pass | `solution.py` |
| DS-1000 | typed-repair+retain | pass | `solution.py` |
| MLAgentBench | gated-resample | pass | `research_plan.json` |
| MLAgentBench | typed-repair+retain | pass | `research_plan.json` |

The smoke run uses the dummy client, so it validates adapters, gates, artifacts, and aggregation. It is not model-performance evidence.

## Interpretation For The Paper

These integrations enable the next paper lanes:

1. SWE-bench Lite/Verified subset for patch-artifact workflow validity.
2. DS-1000 for executable data-science code repair.
3. MLAgentBench for ML research workflow integration and official upstream scoring.

The immediate strongest next run is DS-1000 because it has an executable local oracle and does not require Docker/Kaggle orchestration. SWE-bench and MLAgentBench require official external runners before their results can be cited as benchmark scores.

## Official Runner Bridge

Follow-up bridge code now converts preserved VeriHarness traces into official runner inputs:

- SWE-bench: `export-swebench-predictions` writes official `instance_id` / `model_name_or_path` / `model_patch` JSONL.
- SWE-bench: `run-swebench-official` prints or executes `swebench.harness.run_evaluation`.
- MLAgentBench: `export-mlagentbench-manifests` materializes `research_plan.json` artifacts and an index.
- MLAgentBench: `run-mlagentbench-official` prints or executes upstream `prepare_task`, `runner`, and `eval` commands.

Bridge report and smoke artifacts:

- `/Users/jaray/Documents/autoresearch/reports/official_runner_bridge.md`
- `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/`

## Recommended Next Commands

DS-1000 local model probe:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_ds1000_subset.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

SWE-bench patch-generation subset, followed by official SWE-bench evaluation:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_swebench_subset.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

MLAgentBench manifest probe:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_mlagentbench_subset.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

For paper claims, report SWE-bench and MLAgentBench only after their upstream evaluators are run.
