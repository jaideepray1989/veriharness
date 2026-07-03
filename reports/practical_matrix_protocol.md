# Practical VeriHarness Run Matrix

This protocol is the next paper-quality evaluation matrix. It is designed to
separate four claims that were previously entangled:

- generation/acceptance separation,
- generic retry versus typed repair,
- capability thresholds across model families,
- context-state claims versus direct context-bloat measurements.

## Primary Matrix

Primary evaluation is oracle-blind for online acceptance: gates may validate
schema, artifacts, deterministic visible checks, evidence, and verifier signals,
but hidden benchmark oracles are used only post-hoc to score results.

| Axis | Setting |
|---|---|
| Verifiable leaf tasks | 150 per seed |
| Long-horizon workflow tasks | 30 per seed |
| Seeds | 1, 2, 3 |
| Models | 3 local models from distinct family/capability groups |
| Variants | H0, H3, generic-retry, H4 |
| Call budgets | 1, 2, 4 leaf calls per task |
| Primary acceptance | Oracle-blind |
| Upper bound | Oracle-guided runs reported separately only as an upper bound |

The configured 150 leaf tasks per seed are:

| Benchmark | Tasks per seed |
|---|---:|
| BoolQ | 20 |
| SQuAD | 20 |
| SciQ | 20 |
| ARC-Easy | 20 |
| GLUE SST-2 | 20 |
| GLUE RTE | 20 |
| GLUE MRPC | 20 |
| TREC-QC | 10 |

The configured 30 workflow tasks per seed use `mini_workflow`.

## Variants

| Variant | Meaning |
|---|---|
| H0 | Full/raw context, leaf self-acceptance, oracle post-hoc only. |
| H3 | State context with external non-oracle gates; no failure-conditioned repair. Extra call budget permits resampling under gates. |
| generic-retry | State context with external non-oracle gates and generic retry feedback. The retry does not expose typed gate failures or oracle failures. |
| H4 | State context with external non-oracle gates, candidate selection, and typed failure-conditioned repair. |

## Call Budget

`budget.max_leaf_calls_per_task` is the equal-compute control. H4 may spend that
budget on multiple candidates and typed repair attempts. `generic-retry` spends
the same budget on sequential generic retries. H3 may spend the budget on gated
resampling without repair feedback. H0 ignores budgets above 1 because leaf
self-acceptance has no retry controller.

## Model Set

Use three local models that differ by family/capability:

```text
local_ollama_llama              # llama3.1:8b, general dense model
local_ollama_qwen_coder_14b     # qwen2.5-coder:14b, code-specialized model
local_ollama_gpt_oss_20b        # gpt-oss:20b, reasoning/MoE family
```

## Runnable Configs

Primary oracle-blind configs:

```text
configs/experiment_practical_matrix_budget_1.yaml
configs/experiment_practical_matrix_budget_2.yaml
configs/experiment_practical_matrix_budget_4.yaml
```

Oracle-guided upper-bound configs:

```text
configs/experiment_practical_matrix_oracle_guided_upper_bound_budget_1.yaml
configs/experiment_practical_matrix_oracle_guided_upper_bound_budget_2.yaml
configs/experiment_practical_matrix_oracle_guided_upper_bound_budget_4.yaml
```

Run command template:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_budget_1.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_llama,local_ollama_qwen_coder_14b,local_ollama_gpt_oss_20b \
  --backend local
```

Repeat for budgets 2 and 4, then repeat with the oracle-guided upper-bound
configs. Primary and upper-bound runs must not be merged when stating headline
claims.

## Claim Decision Rules

The paper claim should follow the matrix result, not the intended mechanism:

| Result pattern | Paper framing |
|---|---|
| H4 beats generic-retry under equal call budget | Lead with typed failure-conditioned repair. |
| H3 wins but H4 does not | Lead with separation of generation and acceptance. |
| Gains occur mostly on executable/artifact tasks | Narrow scope to verifiable code and artifact workflows. |
| Repair helps only stronger models | Lead with a capability-threshold result. |
| Structured state does not win the direct context experiment | Remove or soften the context-bloat claim. |
| No operational/deployment data exists | Do not present the work as an industry deployment paper. |

## Reporting Requirements

For each model, budget, benchmark family, and variant, report:

- success rate with bootstrap confidence intervals,
- total leaf calls and leaf calls per success,
- retry count and accepted-by-gate rate,
- self-biased acceptance and wrong-claim acceptance rates,
- oracle-blind primary score,
- oracle-guided upper-bound score in a separate table.

The strongest acceptable workshop claim before running this matrix is:

> VeriHarness provides an auditable experimental harness for testing whether
> external acceptance, generic retry, and typed repair improve verifiable leaf
> and workflow tasks under equal local-compute budgets.

Stronger claims require this matrix to support them.
