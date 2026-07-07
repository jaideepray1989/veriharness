# Oracle-Blind Evaluation Results

Date: 2026-07-07

Purpose: collect the completed primary oracle-blind VeriHarness runs for paper use. In these runs, online acceptance does not use the hidden oracle. The oracle is added post-hoc for scoring only.

## Definition

Oracle-blind primary evaluation means:

- `evaluation.oracle_guided_acceptance: false`
- gated variants use schema, artifact, evidence, deterministic, and verifier gates for online acceptance
- hidden oracle results are appended post-hoc with `used_for_acceptance: false`
- repair feedback cannot use hidden oracle failures

This is the correct primary evidence for the VeriHarness paper. Oracle-guided rows should be reported only as upper bounds.

## Completed Primary Runs

| Model | Budget | Rows | Run path |
|---|---:|---:|---|
| `qwen2.5-coder:14b` | 1 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_1_local_ollama_qwen_coder_14b-20260620T073838Z` |
| `qwen2.5-coder:14b` | 2 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_2_local_ollama_qwen_coder_14b` |
| `qwen2.5-coder:14b` | 3 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_3_local_ollama_qwen_coder_14b` |
| `qwen2.5-coder:14b` | 4 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b` |
| `qwen2.5-coder:7b` | 3 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_3_local_ollama_qwen_coder_7b` |
| `qwen2.5:7b` | 3 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_3_local_ollama_qwen` |
| `llama3.1:8b` | 1 | 2160/2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_1_local_ollama_llama` |

I also started the missing budget-1 `qwen2.5:7b` cell, but stopped it after 24/2160 rows because throughput was roughly 6 seconds per row. The partial run is preserved at `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_1_local_ollama_qwen` and should not be cited as a completed result.

## Qwen2.5-Coder 14B Budget Sweep

Each cell is 540 matched task instances per variant.

| Budget | Variant | Success, 95% bootstrap CI | Leaf calls | Premature wrong done | MiniWorkflow |
|---:|---|---:|---:|---:|---:|
| 1 | H0 | 406/540, CI [71.5%, 78.7%] | 540 | 103 | 0/90 |
| 1 | H3 | 420/540, CI [74.3%, 81.1%] | 540 | 113 | 18/90 |
| 1 | `generic-retry` | 426/540, CI [75.6%, 82.0%] | 540 | 107 | 18/90 |
| 1 | H4 | 423/540, CI [75.0%, 81.7%] | 540 | 110 | 18/90 |
| 2 | H0 | 404/540, CI [71.1%, 78.3%] | 540 | 74 | 0/90 |
| 2 | H3 | 419/540, CI [74.1%, 80.9%] | 620 | 112 | 18/90 |
| 2 | `generic-retry` | 430/540, CI [76.3%, 83.0%] | 619 | 99 | 18/90 |
| 2 | H4 | 422/540, CI [74.6%, 81.7%] | 620 | 109 | 18/90 |
| 3 | H0 | 404/540, CI [71.1%, 78.3%] | 540 | 74 | 0/90 |
| 3 | H3 | 419/540, CI [74.1%, 80.9%] | 700 | 112 | 18/90 |
| 3 | `generic-retry` | 428/540, CI [75.9%, 82.6%] | 694 | 101 | 18/90 |
| 3 | H4 | 502/540, CI [90.4%, 95.2%] | 700 | 38 | 90/90 |
| 4 | H0 | 404/540, CI [71.1%, 78.3%] | 540 | 74 | 0/90 |
| 4 | H3 | 418/540, CI [74.1%, 80.6%] | 783 | 112 | 17/90 |
| 4 | `generic-retry` | 426/540, CI [75.4%, 82.2%] | 772 | 103 | 17/90 |
| 4 | H4 | 502/540, CI [90.4%, 95.2%] | 700 | 38 | 90/90 |

Paired H4 vs `generic-retry` on Qwen2.5-Coder 14B:

| Budget | Delta | 95% paired bootstrap CI | McNemar exact p |
|---:|---:|---:|---:|
| 1 | -0.6 pp | [-1.3, 0.0] pp | 0.2500 |
| 2 | -1.5 pp | [-2.8, -0.6] pp | 0.0078 |
| 3 | +13.7 pp | [+10.9, +16.7] pp | 1.4e-19 |
| 4 | +14.1 pp | [+11.1, +17.0] pp | 3.8e-20 |

Interpretation: H4 is not better at tight budgets. The typed/candidate repair benefit appears at budget 3 and remains at budget 4, concentrated in MiniWorkflow.

## Budget-3 Multi-Model Replication

Each model has 540 matched task instances per variant.

| Model | Variant | Success, 95% bootstrap CI | Leaf calls | Premature wrong done | MiniWorkflow |
|---|---|---:|---:|---:|---:|
| `qwen2.5-coder:14b` | H3 | 419/540, CI [74.1%, 80.9%] | 700 | 112 | 18/90 |
| `qwen2.5-coder:14b` | `generic-retry` | 428/540, CI [75.9%, 82.6%] | 694 | 101 | 18/90 |
| `qwen2.5-coder:14b` | H4 | 502/540, CI [90.4%, 95.2%] | 700 | 38 | 90/90 |
| `qwen2.5-coder:7b` | H3 | 365/540, CI [63.7%, 70.9%] | 760 | 146 | 0/90 |
| `qwen2.5-coder:7b` | `generic-retry` | 383/540, CI [66.9%, 74.3%] | 741 | 151 | 0/90 |
| `qwen2.5-coder:7b` | H4 | 472/540, CI [84.4%, 89.8%] | 768 | 55 | 90/90 |
| `qwen2.5:7b` | H3 | 415/540, CI [73.9%, 80.7%] | 668 | 62 | 90/90 |
| `qwen2.5:7b` | `generic-retry` | 431/540, CI [76.3%, 82.6%] | 643 | 93 | 74/90 |
| `qwen2.5:7b` | H4 | 451/540, CI [80.7%, 86.3%] | 665 | 63 | 90/90 |

Paired H4 vs `generic-retry` at budget 3:

| Model | Delta | 95% paired bootstrap CI | McNemar exact p |
|---|---:|---:|---:|
| `qwen2.5-coder:14b` | +13.7 pp | [+10.9, +16.7] pp | 1.4e-19 |
| `qwen2.5-coder:7b` | +16.5 pp | [+13.0, +19.8] pp | 7.4e-26 |
| `qwen2.5:7b` | +3.7 pp | [+1.9, +5.4] pp | 3.6e-05 |

Interpretation: H4 beats generic retry at budget 3 across all three Qwen-family completed lanes, with the strongest effect on coder models and MiniWorkflow.

## Negative Capability Check

`llama3.1:8b` at budget 1 is complete and shows that H4 can fail under weak capability or tight budget:

| Variant | Success, 95% bootstrap CI |
|---|---:|
| H0 | 124/540, CI [19.4%, 26.7%] |
| H3 | 130/540, CI [20.0%, 27.2%] |
| `generic-retry` | 81/540, CI [12.0%, 17.8%] |
| H4 | 0/540, CI [0.0%, 0.0%] |

This supports a capability-threshold caveat: VeriHarness repair should not be claimed as uniformly beneficial for all local models and all budgets.

## Paper Claim Supported By These Runs

The oracle-blind evidence supports:

> VeriHarness improves verifiable LLM workflows when the model and call budget are sufficient, primarily by combining external gates with failure-conditioned repair on artifact/workflow tasks.

The evidence does not support:

- a claim that H4 wins at budget 1 or 2
- a claim that typed repair helps every model
- a headline context-bloat claim from the practical matrix
- using oracle-guided rows as operational deployment evidence

## Remaining Paper Matrix Cells

For a perfectly rectangular matrix, the remaining missing full cells are:

- `qwen2.5:7b`: budgets 1, 2, and 4
- `qwen2.5-coder:7b`: budgets 1, 2, and 4
- `llama3.1:8b`: budgets 2, 3, and 4

The first missing budget-1 `qwen2.5:7b` attempt was started on 2026-07-07 and stopped at 24/2160 rows because the projected runtime was several hours per 2160-row run.
