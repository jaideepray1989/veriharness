# Budget 8/16 Verification

Date: 2026-07-07

Purpose: check whether increasing oracle-blind call budgets beyond 4 changes the VeriHarness paper result.

## Configs Added

Full practical-matrix configs:

- `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_8.yaml`
- `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_16.yaml`

MiniWorkflow targeted verification configs:

- `/Users/jaray/Documents/autoresearch/configs/experiment_mini_workflow_budget_8.yaml`
- `/Users/jaray/Documents/autoresearch/configs/experiment_mini_workflow_budget_16.yaml`

For budgets above 4, `max_retries` was increased with the call budget:

| Budget | `max_leaf_calls_per_task` | `max_retries` |
|---:|---:|---:|
| 8 | 8 | 7 |
| 16 | 16 | 15 |

This matters because keeping `max_retries: 3` would make budget 8/16 mostly equivalent to budget 4.

## Full-Run Attempt

Command launched:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_budget_8.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

The run was stopped at 5/2160 rows because throughput projected to many hours for budget 8, before budget 16. The partial rows are preserved locally at:

- `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_8_local_ollama_qwen_coder_14b`

Committed compact copy:

- `/Users/jaray/Documents/autoresearch/reports/data/budget_8_16_verification/full_budget8_partial_results.jsonl`

These partial rows are not citable as full benchmark results.

## Budget-4 Trace Sensitivity Check

Completed baseline inspected:

- `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b`

The key question is which budget-4 failures are online gate rejections that hit the budget cap. Only those rows can possibly benefit from budget 8/16 under oracle-blind acceptance.

| Variant | Failures | Online accepted failures | Gate-rejected failures hitting budget 4 | Hit-budget benchmarks |
|---|---:|---:|---:|---|
| gated-resample | 122 | 41 | 81 | 73 MiniWorkflow, 8 BoolQ client/empty-answer rows |
| `generic-retry` | 114 | 38 | 76 | 73 MiniWorkflow, 3 BoolQ client/empty-answer rows |
| typed-repair+retain | 38 | 38 | 0 | none |

Interpretation:

- typed-repair+retain has no budget-sensitive failures left at budget 4. Its remaining 38 failures are oracle-blind online acceptances that later fail post-hoc oracle scoring, so extra budget cannot trigger repair.
- gated-resample and `generic-retry` do have budget-sensitive MiniWorkflow failures, but they are almost entirely `claim_without_evidence` failures.

MiniWorkflow budget-4 trace stability:

| Variant | Hit-budget MiniWorkflow failures | Attempt-output stability |
|---|---:|---|
| gated-resample | 73 | 71/73 had exactly one repeated output signature across all 4 attempts |
| `generic-retry` | 73 | 54/73 changed wording, but still ended with zero evidence references |

Representative repeated failure:

```json
{"result":"duplicate_ids_preserved","artifact":"workflow_patch.txt"}
```

The output contains the correct result marker and artifact, but claims have no evidence references, so the evidence gate rejects it. More generic calls do not tell the model what evidence field to add.

## Real Budget-8/16 Probes

Targeted probe commands were launched for MiniWorkflow only:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_mini_workflow_budget_8.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_mini_workflow_budget_16.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local \
  --skip-unavailable
```

The probes were stopped after confirming the failure mode because each high-budget gated-resample row takes 40-120 seconds.

Committed compact copies:

- `/Users/jaray/Documents/autoresearch/reports/data/budget_8_16_verification/mini_budget8_probe_results.jsonl`
- `/Users/jaray/Documents/autoresearch/reports/data/budget_8_16_verification/mini_budget16_probe_results.jsonl`

Probe outcomes:

| Probe | Variant | Task | Calls | Result | Failure | Output behavior |
|---|---|---|---:|---|---|---|
| Budget 8 | gated-resample | `mini-workflow-s1-000` | 8 | fail | `claim_without_evidence` | same answer all 8 attempts; zero evidence refs |
| Budget 8 | gated-resample | `mini-workflow-s1-001` | 8 | fail | `claim_without_evidence` | same answer all 8 attempts; zero evidence refs |
| Budget 16 | gated-resample | `mini-workflow-s1-000` | 16 | fail | `claim_without_evidence` | same answer all 16 attempts; zero evidence refs |

The budget-16 probe repeated:

```json
{"result":"duplicate_ids_preserved","artifact":"workflow_patch.txt"}
```

for all 16 attempts, with one claim and zero evidence references on every attempt.

## Verification Conclusion

Increasing call budget beyond 4 does not appear likely to change the completed Qwen2.5-Coder 14B oracle-blind headline result:

- typed-repair+retain already solves 90/90 MiniWorkflow tasks at budgets 3 and 4.
- typed-repair+retain has zero budget-sensitive gate-rejected failures at budget 4.
- gated-resample and `generic-retry` have budget-sensitive MiniWorkflow failures, but the repeated failure is missing evidence references, not missing more attempts.
- Real budget-8 and budget-16 probes confirmed repeated evidence-gate failure on the same task even after 8 and 16 calls.

The paper should not claim a completed full budget-8/16 sweep. It can say:

> We added budget-8 and budget-16 configs and ran targeted high-budget probes. Trace analysis of the completed budget-4 matrix plus real 8/16 probes indicates the budget-3/4 typed-repair+retain plateau is caused by typed-repair+retain solving all gate-repairable MiniWorkflow cases, while remaining failures are oracle-blind online acceptances that cannot trigger additional repair.

For a fully rectangular appendix table, the full budget-8 and budget-16 runs should be executed as overnight/batch jobs, not interactively.
