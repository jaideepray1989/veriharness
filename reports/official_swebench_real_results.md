# Official SWE-bench Results

Date: 2026-07-08

Purpose: run the real upstream SWE-bench evaluator against VeriHarness-exported predictions.

## Evaluator

The local Mac is `arm64` and has no Docker binary on `PATH`, so the run used the official SWE-bench Modal path:

```bash
.venv-swebench/bin/python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite \
  --split test \
  --predictions_path <prediction_jsonl> \
  --max_workers 1 \
  --run_id <run_id> \
  --timeout 1800 \
  --cache_level env \
  --instance_ids <instance_id> \
  --modal true
```

Evaluator environment:

- Python: `/Users/jaray/Documents/autoresearch/.venv-swebench`
- SWE-bench package: `swebench 4.1.0`
- Modal profile: `jaideepray1989`
- Modal app URL for the completed reference-patch run: `https://modal.com/apps/jaideepray1989/main/ap-vXWhR5kcnlnxbO73Zc23iT`

## Result 1: Bridge/Reference Patch Validation

This run used the dummy/reference patch exported by the VeriHarness adapter smoke run. It is a real official SWE-bench execution, but it is not model-performance evidence.

| Field | Value |
|---|---|
| Dataset | `princeton-nlp/SWE-bench_Lite` |
| Split | `test` |
| Instance | `django__django-13321` |
| Prediction file | `/Users/jaray/Documents/autoresearch/reports/data/official_runner_bridge_smoke/swebench_lite_H4_predictions.jsonl` |
| `model_name_or_path` | `veriharness-dummy-H4` |
| Run ID | `veriharness_real_swebench_modal_1` |
| Submitted | 1 |
| Completed | 1 |
| Resolved | 1 |
| Unresolved | 0 |
| Empty patches | 0 |
| Errors | 0 |
| Resolved rate | 100.0% |

Artifacts:

- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_modal_h4_1_report.json`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_modal_h4_1_instance_report.json`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_modal_h4_1_summary.json`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/modal_run.log`

The official log shows the patch applied cleanly, Django session tests ran, and the instance was graded `resolved: True`.

## Result 2: CoreAI H4 Attempt

Two CoreAI H4 attempts were run locally before official scoring:

| Config | Instance | Local outcome |
|---|---|---|
| `/Users/jaray/Documents/autoresearch/configs/experiment_swebench_lite_h4_coreai_1.yaml` | `django__django-13321` | CoreAI context overflow: 11,446 tokens vs 4,096-token limit. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_swebench_lite_h4_coreai_short.yaml` | `django__django-13447` | CoreAI returned no complete `LeafOutput` JSON object; no patch artifact. |

For the short attempt, the empty prediction was exported and passed to the official SWE-bench harness:

| Field | Value |
|---|---|
| Dataset | `princeton-nlp/SWE-bench_Lite` |
| Split | `test` |
| Instance | `django__django-13447` |
| Prediction file | `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_coreai_short_H4_predictions.jsonl` |
| `model_name_or_path` | `veriharness-coreai-H4-short` |
| Run ID | `veriharness_real_swebench_coreai_short_1` |
| Official harness message | `No instances to run.` |
| Empty patches | 1 |
| Resolved | 0 |
| Resolved rate | 0.0% |

Artifacts:

- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_coreai_short_H4_predictions.jsonl`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/swebench_lite_coreai_short_h4_summary.json`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/coreai_short_modal_run.log`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/coreai_h4_seed1_results.jsonl`
- `/Users/jaray/Documents/autoresearch/reports/data/official_swebench_real/coreai_h4_short_results.jsonl`

## Interpretation

The official runner bridge is validated end-to-end: VeriHarness exported a prediction JSONL, the upstream SWE-bench evaluator ran on Modal, applied the patch, executed tests, and wrote an official report.

For paper claims:

- Cite the bridge/reference-patch run only as official-evaluator plumbing validation: `1/1 resolved`.
- Cite the CoreAI H4 attempt as model-result evidence only with the negative result: `0/1 resolved`, because the local CoreAI model emitted no patch.
- Do not claim a positive H4 model result on SWE-bench from this run.
- A paper-quality SWE-bench model result needs a stronger code model, a smaller SWE-bench prompt pack, or repository-retrieval tooling before patch generation.
