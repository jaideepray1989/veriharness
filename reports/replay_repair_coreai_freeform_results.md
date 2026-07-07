# Replay Repair Ablation: CoreAI Freeform

Date: 2026-07-07

Purpose: isolate repair-message content by replaying the same frozen failed first attempt into each repair policy. This run uses only Apple CoreAI Freeform results.

## Definition

Replay repair creates one deterministic failed output per task, evaluates it through the gate stack, and then gives each repair policy exactly one CoreAI Freeform leaf call from that identical failure state. This removes first-attempt generation drift from the ablation: every policy sees the same task, same failed answer, and same gate failure payload.

Configuration:
- Run: `runs/replay_repair_3bench_coreai`
- Committed data bundle: `reports/data/replay_repair_3bench_coreai`
- Config: `configs/experiment_replay_repair_3bench_coreai.yaml`
- Model client: `coreai_freeform`
- Model name: `SystemLanguageModel.default`
- Parameter label in config: `~3B`
- Tasks: 24 total, 8 each from BoolQ, SciQ, and MiniWorkflow
- Policies: `generic-retry`, `generic+diagnostics`, `typed-label-only`, `typed-fields`, `typed-preserve`
- Rows: 120 repair calls, one call per task-policy pair
- Acceptance: oracle-guided, because this ablation tests repair-feedback visibility

## Overall Results

Primary results count CoreAI client/parse failures as failures.

| Policy | Success | Rate | 95% bootstrap CI | Premature wrong done | Client errors |
|---|---:|---:|---:|---:|---:|
| `generic-retry` | 17/24 | 0.708 | [0.500, 0.917] | 7 | 0 |
| `generic+diagnostics` | 19/24 | 0.792 | [0.625, 0.958] | 4 | 1 |
| `typed-label-only` | 19/24 | 0.792 | [0.625, 0.917] | 4 | 1 |
| `typed-fields` | 18/24 | 0.750 | [0.542, 0.917] | 3 | 3 |
| `typed-preserve` | 15/24 | 0.625 | [0.458, 0.792] | 8 | 1 |

Conditional on no CoreAI client/parse error, the rates were:

| Policy | Success without client-error rows |
|---|---:|
| `generic-retry` | 17/24 |
| `generic+diagnostics` | 19/23 |
| `typed-label-only` | 19/23 |
| `typed-fields` | 18/21 |
| `typed-preserve` | 15/23 |

## By Benchmark

| Benchmark | `generic-retry` | `generic+diagnostics` | `typed-label-only` | `typed-fields` | `typed-preserve` |
|---|---:|---:|---:|---:|---:|
| BoolQ | 5/8 | 7/8 | 7/8 | 7/8 | 7/8 |
| SciQ | 4/8 | 6/8 | 4/8 | 5/8 | 8/8 |
| MiniWorkflow | 8/8 | 6/8 | 8/8 | 6/8 | 0/8 |

## Paired Tests

| Comparison | Delta | 95% bootstrap CI | Treatment-only | Baseline-only | McNemar exact p |
|---|---:|---:|---:|---:|---:|
| `generic+diagnostics` vs `generic-retry` | +0.083 | [-0.125, 0.292] | 4 | 2 | 0.6875 |
| `typed-label-only` vs `generic+diagnostics` | 0.000 | [-0.167, 0.167] | 2 | 2 | 1.0000 |
| `typed-fields` vs `typed-label-only` | -0.042 | [-0.167, 0.083] | 1 | 2 | 1.0000 |
| `typed-preserve` vs `typed-fields` | -0.125 | [-0.375, 0.125] | 3 | 6 | 0.5078 |
| `typed-preserve` vs `generic-retry` | -0.083 | [-0.417, 0.250] | 6 | 8 | 0.7905 |

The intervals are wide because this is a 24-task interactive run. Treat the signs and failure modes as ablation evidence, not as publishable significance claims.

## Prompt Token Overhead

| Policy | Avg repair prompt tokens | Delta vs `generic-retry` |
|---|---:|---:|
| `generic-retry` | 548.3 | 0.0 |
| `generic+diagnostics` | 607.3 | +59.0 |
| `typed-label-only` | 537.7 | -10.7 |
| `typed-fields` | 569.7 | +21.3 |
| `typed-preserve` | 835.7 | +287.3 |

`typed-preserve` is much more expensive in prompt tokens, and in this run that extra context did not translate to better aggregate success.

## Failure Taxonomy

Failure counts across all failed repair rows:

| Failure code | Count |
|---|---:|
| `answer_mismatch` | 20 |
| `claim_without_evidence` | 10 |
| `client_error` | 6 |
| `empty_answer` | 6 |
| `artifact_missing` | 6 |
| `expected_substring_missing` | 4 |
| `test_failed` | 4 |

Representative examples:
- BoolQ `generic-retry` failed with `answer_mismatch`: it produced `false` for `boolq-validation-00001`.
- SciQ `generic-retry` and `typed-label-only` failed with `answer_mismatch`: both produced choice `A` for `sciq-validation-00001`.
- MiniWorkflow `typed-preserve` often repaired the result marker but failed evidence, e.g. `{"result":"duplicate_ids_preserved","artifact":"workflow_patch.txt"}` with `claim_without_evidence`.
- MiniWorkflow `typed-fields` had two CoreAI client/parse failures; one row reported `CoreAI response did not contain a complete JSON object`.

## Interpretation

This run supports a narrower thesis than the earlier small CoreAI quick run:

- Replay repair helps expose whether the repair message itself matters. On identical frozen failures, `generic+diagnostics` and `typed-label-only` improved over pure generic retry by +2/24 tasks.
- Raw validation diagnostics were useful overall, but not universally. They improved BoolQ/SciQ relative to generic retry, while MiniWorkflow regressed from 8/8 to 6/8.
- Full typed preserve did not win under CoreAI Freeform. It was perfect on SciQ but failed all 8 MiniWorkflow tasks, mostly because outputs omitted evidence even when the result marker was corrected.
- The strongest publishable claim from this run is not "more typed structure always wins." It is: replay repair reveals policy-specific failure modes, and typed or diagnostic payloads can reduce wrong-answer acceptance on answer tasks, but preserve-set prompts can overconstrain or distract a smaller local model on evidence/artifact workflows.

Next paper-facing step: keep replay repair, add seeds and another model family before claiming robustness.
