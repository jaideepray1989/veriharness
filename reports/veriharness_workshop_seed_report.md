# VeriHarness: A Code-as-Harness Architecture for Verifiable LLM Research Workflows

Status: workshop paper seed  
Date: 2026-06-21  
Repository: `/Users/jaray/Documents/autoresearch`

## Abstract

Long-running LLM research agents can fail in two recurring ways: context bloat, where stale traces and distractors bury active constraints, and self-biased acceptance, where the same model that produced an output prematurely accepts flawed work. VeriHarness is a code-as-harness prototype that keeps orchestration, state, external gates, traces, and repair logic outside the LLM leaf context. The LLM is still used for all leaf actions, but no gated variant lets a leaf decide final acceptance.

We evaluate VeriHarness with causal ablations over deterministic benchmark tasks and local models. The strongest completed practical result is an oracle-blind Qwen2.5-Coder 14B matrix over 540 rows per variant. At call budget 4, typed-repair+retain solves 502/540 (93.0%, 95% bootstrap CI 90.4%-95.2%) with 700 leaf calls, compared with `generic-retry` at 426/540 (78.9%, CI 75.4%-82.2%) with 772 calls and gated-resample at 418/540 (77.4%, CI 74.1%-80.6%) with 783 calls. This typed-repair+retain lift is concentrated in `mini_workflow`, where typed-repair+retain reaches 90/90 versus 17/90 for gated-resample and `generic-retry`. Earlier supporting runs show the same direction at smaller scale: in a full Qwen 7B sweep of 1870 rows, external gates improve success from H2 145/374 (38.8%) to gated-resample 235/374 (62.8%), and typed-repair+retain improves further to 273/374 (73.0%); in a six-model compact matrix, typed-repair+retain solves 85/108 (78.7%, CI 72.2%-86.1%) versus self-accept at 57/108 (52.8%, CI 43.5%-62.0%). The paper claim should therefore lead with typed failure-conditioned repair only for capable models and sufficient budget, and should keep context-bloat evidence framed as diagnostic rather than proven by the practical matrix.

## Paper Calibration Protocol

The paper-quality run matrix is specified in `/Users/jaray/Documents/autoresearch/reports/practical_matrix_protocol.md`.

A primary oracle-blind Qwen2.5-Coder 14B lane is complete for call budgets 1, 2, and 4. Oracle-guided configurations are run as separate upper-bound artifacts and must not be merged into the primary oracle-blind table.

The protocol adds the missing controls:

- 150 verifiable leaf tasks and 30 workflow tasks per seed,
- 3 seeds,
- 3 distinct local model families,
- self-accept, gated-resample, `generic-retry`, and typed-repair+retain,
- call budgets of 1, 2, and 4,
- oracle-blind primary acceptance,
- oracle-guided runs reported separately only as an upper bound.

The headline claim should follow that matrix:

| Result pattern | Paper framing |
|---|---|
| typed-repair+retain beats `generic-retry` under equal call budget | Lead with typed failure-conditioned repair. |
| gated-resample wins but typed-repair+retain does not | Lead with separation of generation and acceptance. |
| Gains occur mostly on executable/artifact tasks | Narrow scope to verifiable code and artifact workflows. |
| Repair helps only stronger models | Lead with a capability-threshold result. |
| Structured state does not win the direct context experiment | Remove or soften the context-bloat claim. |
| No operational/deployment data exists | Do not frame the work as an industry deployment paper. |

Current calibration from the completed Qwen2.5-Coder 14B primary lane:

- typed-repair+retain does not beat `generic-retry` at budgets 1 or 2, so low-budget evidence does not support leading with typed repair.
- typed-repair+retain beats `generic-retry` decisively at budget 4 under lower total calls, so the budget-4 result supports a typed-repair claim for a capable local model.
- The gain is mostly on executable/artifact workflow tasks, so the scope should emphasize verifiable code and artifact workflows.
- The practical matrix has zero measured context-bloat proxy events, so context bloat should not be a headline causal claim from this matrix.

## Thesis

VeriHarness tests the claim that long-horizon LLM workflows are more reliable when the system separates:

- leaf generation from final acceptance,
- context packing from raw transcript accumulation,
- deterministic gates from model self-assessment,
- trace preservation from prompt stuffing,
- repair feedback from unstructured retries.

The central hypothesis is:

> A code-as-harness design with state context, external gates, preserved traces, and gate-conditioned repair reduces context bloat and self-biased acceptance relative to self-accepting autoresearch harnesses, at the cost of additional leaf calls.

## System Definition

### Architecture

VeriHarness is a Python orchestrator around LLM leaf calls. The orchestrator schedules tasks, constructs context packs, calls LLM leaves, writes traces, evaluates gates, and decides acceptance. The LLM performs leaf actions only.

```text
TaskSpec
  -> Python Orchestrator
      -> StateStore
      -> ContextPack
      -> LeafRunner / LLM leaf call
      -> LeafOutput
      -> GateStack
      -> ExperimentResult
      -> traces and aggregate tables
```

### Principal Researcher And Workers

The repository contains two related harness layers:

- `autoresearch/`: a principal researcher and worker-pool prototype for research plans. It writes compact JSON artifacts and a synthesized report.
- `veriharness/`: the experimental harness used for causal ablation. It treats every task/variant pair as a controlled leaf action with preserved traces and deterministic gates.

For paper results, the operative experimental principal is the Python `Orchestrator`, and the workers are LLM leaves invoked through `LeafRunner`. This is intentional: the paper is about code-as-harness control, not an unconstrained product agent framework.

### Leaf Action

A leaf action is one LLM call over a `LeafRequest`, containing:

- `context_pack`: task objective, active state, accepted/rejected facts, constraints, distractors, output schema, and budget.
- `task`: deterministic `TaskSpec`.
- `attempt`: retry index.
- `candidate_id`: candidate identifier.
- `retry_feedback`: gate-conditioned feedback from previous failures.

The leaf must return structured `LeafOutput`:

- `task_id`
- `answer`
- `artifacts`
- `claims`
- `self_assessment`
- `done`

All leaf prompts, transcripts, parsed outputs, gate results, and metadata are written under `runs/<run_id>/artifacts/leaves/...`.

### Gate Stack

Gated variants use the `GateStack`:

| Gate | Hard? | Purpose |
|---|---:|---|
| SchemaGate | yes | Checks task id, parse/client errors, and empty answers. |
| ArtifactGate | yes | Checks required artifact declarations and written files. |
| EvidenceGate | yes | Requires explicit claims with evidence references unless disabled. |
| DeterministicGate | yes | Checks deterministic string/JSON constraints. |
| OracleGate | yes | Evaluates hidden benchmark oracle. |
| LLMVerifierGate | no | Records soft verifier-style risk flags. |

Only hard gate success can accept a gated task.

## Ablation Definitions

The intended causal ablation is:

| Variant | Definition | Acceptance |
|---|---|---|
| self-accept | Full raw trace + self accept | Leaf `done` controls agent acceptance; oracle is post-hoc. |
| H1 | Summary context + self accept | Leaf `done` controls agent acceptance; oracle is post-hoc. |
| H2 | State context + self accept | Leaf `done` controls agent acceptance; oracle is post-hoc. |
| gated-resample | State context + external gates | Gate stack controls final acceptance. |
| typed-repair+retain | State context + external gates + VeriHarness | Gate stack controls final acceptance with candidate selection and repair. |

The repair-factor ablation adds these variants:

| Variant | Isolated factor | Definition |
|---|---|---|
| `generic-retry` | Retry without failure details | State context plus external gates; retry prompt says only that acceptance checks failed. |
| `natural-retry` | More information without typed structure | Verbalizes readable gate messages in natural language without typed `gate.code` payloads. |
| `retain+generic` | Candidate retention | Uses typed-repair+retain-style candidate retention with generic retry feedback. |
| `targeted+untyped` | Target locus selection without typed payloads | Selects a highest-priority repair locus and gives natural-language guidance without typed codes. |
| `typed+no-retain` | Typed payloads without candidate retention | Uses typed gate/failure payloads with one candidate per attempt. |
| typed-repair+retain | Combined policy | Candidate retention plus typed failure-conditioned repair. |

Compact multi-model runs use self-accept, gated-resample, typed-repair+retain. The huge Qwen 7B sweep uses self-accept through typed-repair+retain. The repair-factor ablation uses gated-resample, `generic-retry`, `natural-retry`, `retain+generic`, `targeted+untyped`, `typed+no-retain`, and typed-repair+retain.

## Metrics

| Metric | Definition |
|---|---|
| `success` | Final row passes its oracle and, for gated variants, hard external gates. |
| `accepted_by_agent` | Leaf self-assessment marked `done`. |
| `accepted_by_gate` | External gate stack accepted the output. |
| `premature_stop` | Leaf self-accepted but final result failed. Used as self-biased acceptance proxy. |
| `wrong_claim_accepted` | Output accepted a known wrong claim and final result failed. |
| `constraint_violation` | Output violates task constraints when final result failed. |
| `context_bloat_proxy` | Failure reason intersects context/constraint failure codes: `constraint_forgotten`, `required_field_missing`, `distractor_adopted`, `json_field_mismatch`, `expected_substring_missing`, `forbidden_substring_present`. |
| `leaf_calls` | Number of LLM leaf calls for a row. |
| `retries` | Gate-conditioned retry count. |
| `tokens_per_success` | Estimated tokens in plus tokens out divided by successes. |
| `success_rate_ci` | Bootstrap confidence interval from `veriharness.experiments.stats.bootstrap_ci`, seed 1, 200 resamples, alpha 0.05. |
| `paired_policy_tests` | Paired bootstrap delta and exact McNemar test over matched `(benchmark, task_id, seed)` instances. |
| `prompt_token_overhead` | Approximate prompt-token counts from saved leaf `transcript.txt` artifacts, split by variant and retry attempts. |

## Benchmarks

### Public NLP And Coding Tasks

| Benchmark | Task family | Output type |
|---|---|---|
| BoolQ | yes/no reading comprehension | JSON answer/label |
| SQuAD | extractive reading comprehension | JSON answer |
| SciQ | science multiple choice | JSON answer/label |
| ARC-Easy | multiple choice science QA | JSON answer/label |
| GLUE SST-2 | sentiment classification | JSON label |
| GLUE RTE | textual entailment | JSON label |
| GLUE MRPC | paraphrase classification | JSON label |
| TREC-QC | question classification | JSON label |
| HumanEval | coding task | code artifact and tests |

### Harness-Specific Diagnostics

| Benchmark | Purpose |
|---|---|
| ContextTrace | Tests whether active constraints survive distractors and longer traces. |
| ProvenanceBias | Tests whether the same wrong claim is treated differently when attributed to the model's own prior answer versus another source. |
| MiniWorkflow | Tests small workflow-like tasks with deterministic artifact and field checks. |

All benchmark generation is deterministic by seed.

## Experimental Data

### Raw Data Inventory

All row-level data are persisted. The report tables below are compiled from these files.

| Dataset | Rows | Path |
|---|---:|---|
| Six-model compact matrix | 324 | `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled` |
| Six-model compact raw rows | 324 across six `results.jsonl` files | `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_*` |
| Full Qwen 7B sweep | 1870 | `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen/results.jsonl` |
| Full Qwen 7B compiled report | summary | `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen/compiled_results.md` |
| Practical Qwen2.5-Coder 14B primary, budget 1 | 2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_1_local_ollama_qwen_coder_14b-20260620T073838Z/results.jsonl` |
| Practical Qwen2.5-Coder 14B primary, budget 2 | 2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_2_local_ollama_qwen_coder_14b/results.jsonl` |
| Practical Qwen2.5-Coder 14B primary, budget 4 | 2160 | `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/results.jsonl` |
| CoreAI Freeform replay repair ablation | 120 | `/Users/jaray/Documents/autoresearch/runs/replay_repair_3bench_coreai/results.jsonl` |
| CoreAI Freeform replay repair committed data | 120 | `/Users/jaray/Documents/autoresearch/reports/data/replay_repair_3bench_coreai/results.jsonl` |
| Oracle-blind primary evaluation report | summary | `/Users/jaray/Documents/autoresearch/reports/oracle_blind_evaluation_results.md` |
| Budget 8/16 verification | targeted probes and trace analysis | `/Users/jaray/Documents/autoresearch/reports/budget_8_16_verification.md` |
| External benchmark integration | adapter smoke and subset configs | `/Users/jaray/Documents/autoresearch/reports/external_benchmark_integration.md` |
| Official runner bridge | SWE-bench JSONL export and MLAgentBench command-plan smoke | `/Users/jaray/Documents/autoresearch/reports/official_runner_bridge.md` |
| Official SWE-bench run | real Modal evaluator result and CoreAI attempt | `/Users/jaray/Documents/autoresearch/reports/official_swebench_real_results.md` |
| Failure examples | selected examples | `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/failure_examples.md` |
| Baseline comparison | paired self-accept-vs-gated-resample/typed-repair+retain | `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/baseline_comparison.md` |

### Practical Matrix: Qwen2.5-Coder 14B Primary

Config paths:

- `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_1.yaml`
- `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_2.yaml`
- `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_4.yaml`

Role: primary oracle-blind evaluation. The oracle is used post-hoc for scoring and is not exposed to online repair or acceptance. Model: `qwen2.5-coder:14b` through local Ollama, recorded as 14.7B parameters, Q4_K_M quantization.

Benchmarks per seed: BoolQ, SQuAD, SciQ, ARC-Easy, GLUE SST-2, GLUE RTE, GLUE MRPC, TREC-QC, and MiniWorkflow. Each call-budget run contains 150 verifiable leaf tasks and 30 workflow tasks per seed, 3 seeds, and four variants: self-accept, gated-resample, `generic-retry`, typed-repair+retain.

| Budget | Variant | Success, 95% bootstrap CI | Leaf calls | Premature/self-bias proxy | Gate accepts | MiniWorkflow |
|---:|---|---:|---:|---:|---:|---:|
| 1 | self-accept | 406/540 (75.2%, CI 71.5%-78.7%) | 540 | 103 | 0 | 0/90 |
| 1 | gated-resample | 420/540 (77.8%, CI 74.3%-81.1%) | 540 | 113 | 461 | 18/90 |
| 1 | `generic-retry` | 426/540 (78.9%, CI 75.6%-82.0%) | 540 | 107 | 461 | 18/90 |
| 1 | typed-repair+retain | 423/540 (78.3%, CI 75.0%-81.7%) | 540 | 110 | 461 | 18/90 |
| 2 | self-accept | 404/540 (74.8%, CI 71.1%-78.3%) | 540 | 74 | 0 | 0/90 |
| 2 | gated-resample | 419/540 (77.6%, CI 74.1%-80.9%) | 620 | 112 | 460 | 18/90 |
| 2 | `generic-retry` | 430/540 (79.6%, CI 76.3%-83.0%) | 619 | 99 | 465 | 18/90 |
| 2 | typed-repair+retain | 422/540 (78.1%, CI 74.6%-81.7%) | 620 | 109 | 460 | 18/90 |
| 4 | self-accept | 404/540 (74.8%, CI 71.1%-78.3%) | 540 | 74 | 0 | 0/90 |
| 4 | gated-resample | 418/540 (77.4%, CI 74.1%-80.6%) | 783 | 112 | 459 | 17/90 |
| 4 | `generic-retry` | 426/540 (78.9%, CI 75.4%-82.2%) | 772 | 103 | 464 | 17/90 |
| 4 | typed-repair+retain | 502/540 (93.0%, CI 90.4%-95.2%) | 700 | 38 | 540 | 90/90 |

Practical-matrix interpretation:

- At budgets 1 and 2, `generic-retry` is slightly ahead of typed-repair+retain. This argues against a broad typed-repair claim at tight call budgets.
- At budget 4, typed-repair+retain beats `generic-retry` by 76 successes and 14.1 percentage points while using 72 fewer leaf calls. This supports the typed failure-conditioned repair claim under sufficient budget.
- The budget-4 typed-repair+retain gain is mostly the MiniWorkflow jump from 17/90 to 90/90. The paper should therefore narrow the headline to verifiable code/artifact workflows rather than claiming uniform NLP benchmark gains.
- The practical-matrix context-bloat proxy is 0 across variants. Context bloat remains supported only by diagnostic runs, not by this practical primary matrix.
- Oracle-guided upper-bound configs are separate from these primary rows. The budget-1 oracle-guided run completed in `/Users/jaray/Documents/autoresearch/runs/practical_matrix_oracle_guided_upper_bound_budget_1_local_ollama_qwen_coder_14b`; budget-2 and budget-4 upper-bound rows remain separate pending work.

### Budget-3 Replication

The first budget-3 primary oracle-blind replication completed for Qwen2.5-Coder 14B. It uses the seed-safe trace layout introduced for reviewer feedback, so prompt-overhead accounting is complete for this run.

| Model | Variant | Success, 95% bootstrap CI | Leaf calls | Prompt tokens | MiniWorkflow |
|---|---|---:|---:|---:|---:|
| qwen2.5-coder:14b | self-accept | 404/540 (74.8%, CI 71.1%-78.3%) | 540 | 231,556 | 0/90 |
| qwen2.5-coder:14b | gated-resample | 419/540 (77.6%, CI 74.1%-80.9%) | 700 | 282,224 | 18/90 |
| qwen2.5-coder:14b | `generic-retry` | 428/540 (79.3%, CI 75.9%-82.6%) | 694 | 300,421 | 18/90 |
| qwen2.5-coder:14b | typed-repair+retain | 502/540 (93.0%, CI 90.4%-95.2%) | 700 | 304,910 | 90/90 |

Paired budget-3 result: typed-repair+retain beats `generic-retry` by +13.7 percentage points on matched instances, with 95% paired bootstrap CI +10.9 to +16.7 points and exact McNemar p=1.4e-19. Relative to `generic-retry`, typed-repair+retain adds about 4,489 prompt tokens across the whole run and about 153 prompt tokens per retry prompt on average, but solves 74 more rows.

The budget-3 multi-model command is still running for `qwen2.5-coder:7b` and `qwen2.5:7b`.

### CoreAI Freeform Replay Repair Ablation

Replay repair freezes one deterministic failed first attempt per task, then gives every repair policy exactly one CoreAI Freeform repair call from that identical failure state. This isolates repair-message content from first-attempt generation drift. The full report is `/Users/jaray/Documents/autoresearch/reports/replay_repair_coreai_freeform_results.md`.

Config: `/Users/jaray/Documents/autoresearch/configs/experiment_replay_repair_3bench_coreai.yaml`

Run: `/Users/jaray/Documents/autoresearch/runs/replay_repair_3bench_coreai`

Committed compact data: `/Users/jaray/Documents/autoresearch/reports/data/replay_repair_3bench_coreai`

| Policy | Success, 95% bootstrap CI | Premature wrong done | Client errors |
|---|---:|---:|---:|
| `generic-retry` | 17/24 (70.8%, CI 50.0%-91.7%) | 7 | 0 |
| `generic+diagnostics` | 19/24 (79.2%, CI 62.5%-95.8%) | 4 | 1 |
| `typed-label-only` | 19/24 (79.2%, CI 62.5%-91.7%) | 4 | 1 |
| `typed-fields` | 18/24 (75.0%, CI 54.2%-91.7%) | 3 | 3 |
| `typed-preserve` | 15/24 (62.5%, CI 45.8%-79.2%) | 8 | 1 |

By benchmark: BoolQ favored diagnostics/typed variants at 7/8 versus `generic-retry` at 5/8; SciQ favored `typed-preserve` at 8/8; MiniWorkflow rejected `typed-preserve` at 0/8 because it often fixed the result marker but omitted explicit evidence. The paper should use this as a diagnostic caution: typed or diagnostic payloads can reduce wrong-answer acceptance, but full preserve-set prompting is not uniformly better on CoreAI Freeform.

### Reviewer Feedback Response Plan

This section tracks concrete changes made in response to expected workshop-reviewer questions.

| Feedback | Current answer or action |
|---|---|
| Disentangle candidate retention, targeted locus selection, and typed payloads. | Added explicit variants: `retain+generic`, `targeted+untyped`, `typed+no-retain`, and `natural-retry`. Full config: `/Users/jaray/Documents/autoresearch/configs/experiment_repair_factor_ablation_budget_4.yaml`. |
| How is the repair target selected when multiple gates fail? | typed-repair+retain and `typed+no-retain` expose all visible non-oracle failures in deterministic gate order. `targeted+untyped` uses a deterministic single-locus priority heuristic: schema/client problems, artifact, evidence, code/test execution, deterministic constraints, provenance, answer mismatch. No learned policy is used. |
| What decoding settings are used? | Local Ollama runs use temperature `0.0`; `top_p` is unset unless explicitly configured. CoreAI uses greedy sampling in the Swift bridge. Result rows now record `temperature`, `top_p`, and `max_output_tokens` in metadata. No systematic decoding-sensitivity sweep has been run yet. |
| Add a natural-language gate-error baseline. | Added `natural-retry`, which includes readable gate messages but avoids typed failure codes such as `artifact_missing` or `evidence.claim_without_evidence`. |
| Measure typed repair token overhead. | Aggregation now writes `prompt_token_overhead.csv` from saved leaf transcripts. Legacy budget-4 artifacts undercount prompt traces because old paths collided across seeds; new runs include benchmark and seed in artifact paths, so budget-3 and ablation runs will have complete prompt-overhead accounting. |
| Provide per-seed results and paired tests. | Aggregation now writes `per_seed_results.csv` and `paired_policy_tests.csv`. Paired tests use matched `(benchmark, task_id, seed)` instances and report paired bootstrap delta CIs plus exact McNemar p-values. |
| Handle nondeterministic tests/flaky tooling. | Current public NLP and MiniWorkflow gates are deterministic. HumanEval candidates run in a fresh temporary subprocess with a timeout and captured stderr/stdout. Safeguards against oscillation are fixed call budgets, retry caps, preserved traces, and final gate-only acceptance. A flaky-test quarantine/retry-classifier is not yet implemented. |
| Run budget 3 and multi-model replication. | Added `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_3.yaml`. A primary oracle-blind multi-model run has been launched for `qwen2.5-coder:14b`, `qwen2.5-coder:7b`, and `qwen2.5:7b`. |

### Paired Statistics From Completed Budget 4

The refreshed budget-4 aggregate now includes seed-aware paired tests. Key primary comparisons:

| Comparison | Treatment success | Baseline success | Delta | 95% paired bootstrap CI | McNemar exact p |
|---|---:|---:|---:|---:|---:|
| typed-repair+retain vs `generic-retry` | 502/540 | 426/540 | +14.1 pp | +11.1 to +17.0 pp | 3.8e-20 |
| typed-repair+retain vs gated-resample | 502/540 | 418/540 | +15.6 pp | +12.4 to +18.3 pp | 1.0e-25 |
| `generic-retry` vs gated-resample | 426/540 | 418/540 | +1.5 pp | +0.6 to +2.8 pp | 0.021 |

Per-seed typed-repair+retain budget-4 success is stable: seed 1 is 168/180, seed 2 is 168/180, and seed 3 is 166/180.

### Compact Model Matrix Configuration

Config: `/Users/jaray/Documents/autoresearch/configs/experiment_model_matrix_probe.yaml`

- Benchmarks: BoolQ, SQuAD, SciQ, ARC-Easy, GLUE RTE, TREC-QC, ContextTrace, ProvenanceBias, MiniWorkflow.
- Tasks: 2 per benchmark, seed 1.
- Variants: self-accept, gated-resample, typed-repair+retain.
- Budget: `max_retries=2`, `veriharness_k=2`, `max_leaf_calls_per_task=6`, `max_wall_time_seconds=900`.
- Models: five Qwen checkpoints plus one Llama comparator through local Ollama.

### Compact Model Matrix Models

| Model | Params | Rows | Complete | Solve, 95% bootstrap CI | Leaf calls | Retries | Avg sec/row |
|---|---:|---:|---|---:|---:|---:|---:|
| qwen2.5:3b | 3B | 54/54 | true | 16/54 (29.6%, CI 18.5%-40.7%) | 165 | 63 | 4.6 |
| qwen2.5:7b | 7.6B | 54/54 | true | 45/54 (83.3%, CI 74.1%-92.6%) | 79 | 15 | 7.2 |
| qwen2.5:14b | 14.7B | 54/54 | true | 48/54 (88.9%, CI 77.8%-94.4%) | 77 | 16 | 15.4 |
| qwen2.5-coder:7b | 7.6B coder | 54/54 | true | 41/54 (75.9%, CI 64.8%-87.0%) | 106 | 27 | 8.8 |
| qwen2.5-coder:14b | 14.7B coder | 54/54 | true | 50/54 (92.6%, CI 83.3%-98.1%) | 74 | 12 | 15.5 |
| llama3.1:8b | 8B | 54/54 | true | 26/54 (48.1%, CI 35.2%-59.3%) | 127 | 42 | 57.8 |

### Compact Matrix Variant Results

| Model | Variant | Solve, 95% bootstrap CI | Avg calls | Retries | Gate no self-accept | Premature | Context bloat | Wrong claim |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| qwen2.5:3b | self-accept | 3/18 (16.7%, CI 0.0%-33.3%) | 1.00 | 0 | 0 | 0 | 1 | 0 |
| qwen2.5:3b | gated-resample | 7/18 (38.9%, CI 16.7%-61.1%) | 2.67 | 30 | 6 | 0 | 2 | 0 |
| qwen2.5:3b | typed-repair+retain | 6/18 (33.3%, CI 16.7%-55.6%) | 5.50 | 33 | 4 | 0 | 2 | 0 |
| qwen2.5:7b | self-accept | 12/18 (66.7%, CI 44.4%-83.3%) | 1.00 | 0 | 0 | 2 | 0 | 0 |
| qwen2.5:7b | gated-resample | 16/18 (88.9%, CI 72.2%-100.0%) | 1.56 | 10 | 3 | 1 | 0 | 0 |
| qwen2.5:7b | typed-repair+retain | 17/18 (94.4%, CI 83.3%-100.0%) | 1.83 | 5 | 3 | 0 | 0 | 0 |
| qwen2.5:14b | self-accept | 14/18 (77.8%, CI 55.6%-94.4%) | 1.00 | 0 | 0 | 1 | 1 | 0 |
| qwen2.5:14b | gated-resample | 16/18 (88.9%, CI 72.2%-100.0%) | 1.56 | 10 | 4 | 2 | 2 | 0 |
| qwen2.5:14b | typed-repair+retain | 18/18 (100.0%, CI 100.0%-100.0%) | 1.72 | 6 | 6 | 0 | 0 | 0 |
| qwen2.5-coder:7b | self-accept | 10/18 (55.6%, CI 27.8%-77.8%) | 1.00 | 0 | 0 | 1 | 0 | 0 |
| qwen2.5-coder:7b | gated-resample | 15/18 (83.3%, CI 66.7%-100.0%) | 1.78 | 14 | 1 | 1 | 0 | 0 |
| qwen2.5-coder:7b | typed-repair+retain | 16/18 (88.9%, CI 72.2%-100.0%) | 3.11 | 13 | 2 | 0 | 1 | 0 |
| qwen2.5-coder:14b | self-accept | 14/18 (77.8%, CI 55.6%-94.4%) | 1.00 | 0 | 0 | 3 | 0 | 0 |
| qwen2.5-coder:14b | gated-resample | 18/18 (100.0%, CI 100.0%-100.0%) | 1.39 | 7 | 2 | 0 | 0 | 0 |
| qwen2.5-coder:14b | typed-repair+retain | 18/18 (100.0%, CI 100.0%-100.0%) | 1.72 | 5 | 2 | 0 | 0 | 0 |
| llama3.1:8b | self-accept | 4/18 (22.2%, CI 5.6%-44.4%) | 1.00 | 0 | 0 | 0 | 1 | 0 |
| llama3.1:8b | gated-resample | 12/18 (66.7%, CI 38.9%-83.3%) | 2.22 | 22 | 11 | 0 | 3 | 0 |
| llama3.1:8b | typed-repair+retain | 10/18 (55.6%, CI 27.8%-72.2%) | 3.83 | 20 | 9 | 0 | 2 | 0 |

### Compact Matrix Aggregate By Variant

| Variant | Success | 95% bootstrap CI | Premature | Context bloat proxy | Wrong claim accepted | Leaf-call profile |
|---|---:|---:|---:|---:|---:|---|
| self-accept | 57/108 (52.8%) | 43.5%-62.0% | 7 | 3 | 0 | 108 calls, 0 retries |
| gated-resample | 84/108 (77.8%) | 67.6%-85.2% | 4 | 7 | 0 | 201 calls, 93 retries |
| typed-repair+retain | 85/108 (78.7%) | 72.2%-86.1% | 0 | 5 | 0 | 319 calls, 82 retries |

Interpretation:

- gated-resample provides the main jump over self-accepting self-accept.
- typed-repair+retain removes premature acceptance in this matrix, but only slightly improves aggregate solve over gated-resample because Llama and Qwen 3B are weak under repair pressure.
- typed-repair+retain is strongest on competent models: qwen2.5:14b and qwen2.5-coder:14b both reach 18/18.

## Baseline Comparison

The lightweight baseline is an AutoResearch-style self-accepting code harness:

| Axis | Baseline | VeriHarness typed-repair+retain |
|---|---|---|
| Leaf action | LLM-generated structured output | LLM-generated structured output |
| Acceptance | Leaf/model self-accepts | External gates accept/reject |
| Context | Full accumulated trace | State/context pack |
| Repair | No gate-conditioned repair | Failure-conditioned repair from gate feedback |
| Traceability | Prompts and outputs | Prompts, outputs, gates, events, and retries |

Operationally, the baseline is self-accept: full trace in context, no external gate, and leaf self-assessment controls `done`.

### Paired Baseline Results

| Model | Treatment | Baseline solve | Treatment solve | Delta | Treatment-only | Baseline-only | Premature baseline->treatment | Leaf calls baseline->treatment |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| llama3.1:8b | gated-resample | 4/18 (22.2%) | 12/18 (66.7%) | +44.4 pp | 10 | 2 | 0->0 | 18->40 |
| llama3.1:8b | typed-repair+retain | 4/18 (22.2%) | 10/18 (55.6%) | +33.3 pp | 6 | 0 | 0->0 | 18->69 |
| qwen2.5-coder:14b | gated-resample | 14/18 (77.8%) | 18/18 (100.0%) | +22.2 pp | 4 | 0 | 3->0 | 18->25 |
| qwen2.5-coder:14b | typed-repair+retain | 14/18 (77.8%) | 18/18 (100.0%) | +22.2 pp | 4 | 0 | 3->0 | 18->31 |
| qwen2.5-coder:7b | gated-resample | 10/18 (55.6%) | 15/18 (83.3%) | +27.8 pp | 6 | 1 | 1->1 | 18->32 |
| qwen2.5-coder:7b | typed-repair+retain | 10/18 (55.6%) | 16/18 (88.9%) | +33.3 pp | 7 | 1 | 1->0 | 18->56 |
| qwen2.5:14b | gated-resample | 14/18 (77.8%) | 16/18 (88.9%) | +11.1 pp | 3 | 1 | 1->2 | 18->28 |
| qwen2.5:14b | typed-repair+retain | 14/18 (77.8%) | 18/18 (100.0%) | +22.2 pp | 4 | 0 | 1->0 | 18->31 |
| qwen2.5:3b | gated-resample | 3/18 (16.7%) | 7/18 (38.9%) | +22.2 pp | 4 | 0 | 0->0 | 18->48 |
| qwen2.5:3b | typed-repair+retain | 3/18 (16.7%) | 6/18 (33.3%) | +16.7 pp | 5 | 2 | 0->0 | 18->99 |
| qwen2.5:7b | gated-resample | 12/18 (66.7%) | 16/18 (88.9%) | +22.2 pp | 5 | 1 | 2->1 | 18->28 |
| qwen2.5:7b | typed-repair+retain | 12/18 (66.7%) | 17/18 (94.4%) | +27.8 pp | 5 | 0 | 2->0 | 18->33 |

The baseline comparison supports the harness thesis: typed-repair+retain solves 85/108 (78.7%) versus self-accept baseline 57/108 (52.8%), and premature self-acceptance drops from 7 to 0. It also shows the cost side: typed-repair+retain uses 319 leaf calls compared with 108 for self-accept.

## Full Qwen 7B Sweep

Config: `/Users/jaray/Documents/autoresearch/configs/experiment_huge_full_sweep_local.yaml`  
Run: `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen`  
Rows: 1870/1870  
Model: `qwen2.5:7b`, 7.6B parameters, Q4_K_M via Ollama.

### Full Sweep Variant Summary

| Variant | Meaning | Success | Rate | Leaf calls | Premature/self-bias proxy | Context violations | Gate accepts |
|---|---|---:|---:|---:|---:|---:|---:|
| self-accept | full trace + self accept | 151/374 | 40.4% | 374 | 39 (10.4%) | 1 | 0 |
| H1 | summary + self accept | 137/374 | 36.6% | 374 | 36 (9.6%) | 5 | 0 |
| H2 | state context + self accept | 145/374 | 38.8% | 374 | 19 (5.1%) | 9 | 0 |
| gated-resample | state context + external gates | 235/374 | 62.8% | 802 | 18 (4.8%) | 0 | 235 |
| typed-repair+retain | state context + external gates + VeriHarness | 273/374 | 73.0% | 1221 | 7 (1.9%) | 0 | 273 |

### Full Sweep Benchmark Matrix

| Benchmark | self-accept | H1 | H2 | gated-resample | typed-repair+retain | typed-repair+retain-gated-resample |
|---|---:|---:|---:|---:|---:|---:|
| boolq | 2/20 | 1/20 | 2/20 | 9/20 | 11/20 | +2 |
| squad | 18/20 | 17/20 | 15/20 | 19/20 | 18/20 | -1 |
| sciq | 14/20 | 15/20 | 16/20 | 16/20 | 18/20 | +2 |
| arc_easy | 15/20 | 15/20 | 16/20 | 16/20 | 18/20 | +2 |
| glue_sst2 | 15/20 | 15/20 | 15/20 | 19/20 | 20/20 | +1 |
| glue_rte | 8/20 | 10/20 | 10/20 | 12/20 | 16/20 | +4 |
| glue_mrpc | 12/20 | 12/20 | 13/20 | 15/20 | 18/20 | +3 |
| trec_qc | 18/20 | 18/20 | 16/20 | 19/20 | 19/20 | +0 |
| context_trace | 19/20 | 15/20 | 11/20 | 20/20 | 20/20 | +0 |
| provenance_bias | 12/20 | 7/20 | 17/20 | 19/20 | 20/20 | +1 |
| mini_workflow | 2/10 | 1/10 | 7/10 | 10/10 | 10/10 | +0 |
| humaneval | 16/164 | 11/164 | 7/164 | 61/164 | 85/164 | +24 |

### Full Sweep Thesis Checks

- External gates versus state-context self-accept: H2 145/374 (38.8%) to gated-resample 235/374 (62.8%), +90 successes and +24.1 percentage points.
- VeriHarness candidate selection and repair versus gates only: gated-resample 235/374 (62.8%) to typed-repair+retain 273/374 (73.0%), +38 successes and +10.2 percentage points.
- ContextTrace: self-accept 19/20, H1 15/20, H2 11/20, gated-resample 20/20, typed-repair+retain 20/20.
- ProvenanceBias: self-accept 12/20, H1 7/20, H2 17/20, gated-resample 19/20, typed-repair+retain 20/20.
- HumanEval: self-accept 16/164, H1 11/164, H2 7/164, gated-resample 61/164, typed-repair+retain 85/164.
- Cost: typed-repair+retain uses 1221 leaf calls versus gated-resample 802 and each self-accept variant 374.

## Failure Taxonomy Examples

The following examples are representative rows with preserved artifacts.

### Context Bloat Proxy

- Model: `qwen2.5:3b`
- Variant: self-accept
- Benchmark/task: `context_trace` / `context-trace-s1-000`
- Success: false
- Failure reasons: `constraint_forgotten`, `required_field_missing`
- Artifact: `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_qwen_3b/artifacts/leaves/H0/context-trace-s1-000/attempt_0/candidate_0`

This is the cleanest context-bloat diagnostic. The task requires the leaf to preserve an active constraint, but full-trace self-accept produces an empty or invalid answer.

### Wrong-Claim / Self-Biased Acceptance

- Model: `qwen2.5:7b`
- Variant: self-accept
- Benchmark/task: `provenance_bias` / `provenance-bias-s1-000`
- Success: false
- Accepted by agent: true
- Accepted by gate: false
- Failure reason: `wrong_own_claim_accepted`
- Artifact: `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_qwen/artifacts/leaves/H0/provenance-bias-s1-000/attempt_0/candidate_0`

This illustrates the self-acceptance problem: the leaf marks the task done even though the hidden oracle identifies acceptance of a known wrong claim.

### Missing Artifact Or Evidence

- Model: `qwen2.5:3b`
- Variant: gated-resample
- Benchmark/task: `boolq` / `boolq-validation-00000`
- Success: false
- Retries: 2
- Failure reasons: `client_error`, `empty_answer`, `artifact_missing`, `answer_mismatch`
- Artifact: `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_qwen_3b/artifacts/leaves/H3/boolq-validation-00000/attempt_2/candidate-0`

This illustrates a failure where gates reject malformed or incomplete leaf outputs instead of allowing self-acceptance.

### Gate Repair Success

- Model: `qwen2.5:3b`
- Variant: typed-repair+retain
- Benchmark/task: `squad` / `squad-dev-00000`
- Success: true
- Accepted by agent: false
- Accepted by gate: true
- Retries: 1
- Answer preview: `{"answer":"Denver Broncos"}`
- Artifact: `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_qwen_3b/artifacts/leaves/H4/squad-dev-00000/attempt_1/candidate-1`

This shows the desired separation: the leaf did not self-accept, but the external gate accepted a repaired correct answer.

### Gate Without Self-Accept

- Model: `qwen2.5:3b`
- Variant: gated-resample
- Benchmark/task: `glue_rte` / `glue_rte-validation-00000`
- Success: true
- Accepted by agent: false
- Accepted by gate: true
- Artifact: `/Users/jaray/Documents/autoresearch/runs/model_matrix_probe_local_ollama_qwen_3b/artifacts/leaves/H3/glue_rte-validation-00000/attempt_0/candidate-0`

This shows why leaf self-assessment is not a reliable acceptance signal.

## Discussion

### What The Results Support

1. External gates are the main reliability intervention.
   - Full sweep: H2 38.8% to gated-resample 62.8%.
   - Model matrix: self-accept 52.8% to gated-resample 77.8%.

2. VeriHarness typed-repair+retain improves strong-enough models and removes premature self-acceptance.
   - qwen2.5:14b reaches 18/18 under typed-repair+retain.
   - qwen2.5-coder:14b reaches 18/18 under gated-resample and typed-repair+retain.
   - typed-repair+retain premature self-acceptance is 0 in the six-model matrix.

3. Context bloat is a plausible mechanism, but the current evidence is diagnostic rather than definitive.
   - Full sweep ContextTrace declines across self-accept variants as context is summarized/state-lifted incorrectly: self-accept 19/20, H1 15/20, H2 11/20.
   - gated-resample and typed-repair+retain recover to 20/20 because external gates enforce constraints.
   - The practical Qwen2.5-Coder 14B matrix records 0 context-bloat proxy events, so the context-bloat claim should remain secondary unless a direct context experiment shows structured state winning against raw/summarized context under comparable task pressure.

4. Self-biased acceptance is visible in provenance tasks and premature-stop rates.
   - Full sweep ProvenanceBias improves from self-accept 12/20 to typed-repair+retain 20/20.
   - Compact matrix has explicit wrong/self-biased examples in preserved artifacts.

5. The method has a cost, though the cost profile depends on the repair policy.
   - Full sweep typed-repair+retain uses 1221 leaf calls, compared with gated-resample 802 and self-accept 374.
   - Compact matrix typed-repair+retain uses 319 leaf calls versus self-accept 108.
   - Practical budget-4 typed-repair+retain uses fewer calls than gated-resample and `generic-retry` because typed repair succeeds on workflow tasks without exhausting retries.

### What The Results Do Not Yet Prove

- The compact multi-model matrix has only 18 rows per variant per model. It is useful for model diversity and failure-mode evidence, not for definitive leaderboard claims.
- The full sweep is one main local model family, qwen2.5:7b. It is the stronger causal ablation, but narrower in model diversity.
- Some benchmarks are harness-targeted diagnostics rather than broad open-ended research tasks.
- typed-repair+retain can underperform gated-resample on weaker or less structured models, as seen with llama3.1:8b and qwen2.5:3b.
- The completed practical matrix covers one strong local model lane. A three-family practical run is still needed for a stronger workshop submission.
- Oracle-guided upper-bound configs are not primary evidence and must be reported separately from oracle-blind rows.
- There is no operational deployment dataset. The paper should be framed as a systems/evaluation harness paper, not an industry deployment paper.

## Proposed Workshop Paper Shape

### Title Candidates

- VeriHarness: Code-as-Harness Evaluation for Verifiable LLM Research Workflows
- Separating Generation from Acceptance in Long-Horizon LLM Research Harnesses
- External Gates and Context Packs for Reliable LLM Leaf Actions

### Main Claim

VeriHarness demonstrates that controlled code-as-harness orchestration with external gates and context packs can reduce premature acceptance and improve task success relative to self-accepting autoresearch patterns, with a measurable inference-cost tradeoff.

### Contributions

1. A code-as-harness architecture that keeps LLM work at the leaf level while orchestration, acceptance, and repair remain in code.
2. A causal ablation suite self-accept-typed-repair+retain that separates context representation, self-acceptance, external gates, and VeriHarness repair.
3. Diagnostic benchmarks for context bloat and provenance/self-evaluation bias.
4. Local-model empirical evidence over a 1870-row full sweep and a 324-row six-model matrix.
5. Preserved traces and failure examples suitable for audit and replication.

### Recommended Figure Set

1. Architecture diagram: task, state/context pack, LLM leaf, gates, trace store.
2. Full sweep bar chart: self-accept-typed-repair+retain success rate and leaf calls.
3. Compact model matrix: self-accept/gated-resample/typed-repair+retain success by model.
4. Failure taxonomy panel: context bloat, wrong-claim acceptance, missing artifact/evidence, repair success.

## Reproducibility

### Commands

Run the compact model matrix for the installed local models:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_model_matrix_probe.yaml \
  --models local_ollama_qwen_3b,local_ollama_qwen,local_ollama_qwen_14b,local_ollama_qwen_coder_7b,local_ollama_qwen_coder_14b,local_ollama_llama \
  --backend local
```

Compile workshop artifacts:

```bash
.venv/bin/python -m veriharness.cli.main compile-workshop \
  --run-dirs runs/model_matrix_probe_local_ollama_qwen_3b,runs/model_matrix_probe_local_ollama_qwen,runs/model_matrix_probe_local_ollama_qwen_14b,runs/model_matrix_probe_local_ollama_qwen_coder_7b,runs/model_matrix_probe_local_ollama_qwen_coder_14b,runs/model_matrix_probe_local_ollama_llama \
  --out-dir runs/workshop_model_compiled \
  --expected-rows 54
```

Run or resume the huge sweep:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_huge_full_sweep_local.yaml \
  --models local_ollama_qwen \
  --backend local

.venv/bin/python -m veriharness.cli.main resume-run \
  --run-dir runs/huge_full_sweep_local_local_ollama_qwen
```

Run practical primary matrices and oracle-guided upper-bound lanes:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_budget_4.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local

.venv/bin/python -m veriharness.cli.main aggregate \
  --run-dir runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b

.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_oracle_guided_upper_bound_budget_4.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local
```

Run budget-3 multi-model replication and repair-factor ablation:

```bash
.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_budget_3.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_qwen_coder_14b,local_ollama_qwen_coder_7b,local_ollama_qwen \
  --backend local

.venv/bin/python -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_repair_factor_ablation_budget_4.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_qwen_coder_14b \
  --backend local
```

### Verification

Latest verification run:

```text
.venv/bin/python -m pytest tests/test_harness.py tests/test_experiment_runner.py -q
7 passed

.venv/bin/python -m compileall veriharness
passed
```

## Artifact Appendix

| Artifact | Purpose |
|---|---|
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/workshop_results.md` | Main model and variant tables with bootstrap CIs. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/model_summary.csv` | Model-level compact matrix data. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/variant_summary.csv` | Variant-level compact matrix data. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/benchmark_summary.csv` | Per-model, per-benchmark, per-variant data. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/baseline_comparison.csv` | self-accept versus gated-resample/typed-repair+retain paired baseline data. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/failure_examples.csv` | Representative failure/repair examples. |
| `/Users/jaray/Documents/autoresearch/runs/workshop_model_compiled/combined_aggregate.json` | Aggregate JSON for compact matrix. |
| `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen/results.jsonl` | Full row-level Qwen 7B sweep. |
| `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen/compiled_results.md` | Full sweep summary report. |
| `/Users/jaray/Documents/autoresearch/runs/huge_full_sweep_local_local_ollama_qwen/compiled_benchmark_matrix.csv` | Full sweep benchmark table. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/aggregate.json` | Recomputed budget-4 primary aggregate with typed-repair+retain 502/540 and bootstrap CI. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/results.jsonl` | Row-level budget-4 practical primary data. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/per_seed_results.csv` | Per-seed primary budget-4 summary. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/paired_policy_tests.csv` | Paired bootstrap and McNemar tests for budget-4 primary rows. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/prompt_token_overhead.csv` | Prompt-token overhead table from saved transcripts; legacy budget-4 artifact count is incomplete because old paths collided across repeated task ids. |
| `/Users/jaray/Documents/autoresearch/runs/practical_matrix_oracle_guided_upper_bound_budget_1_local_ollama_qwen_coder_14b/results.jsonl` | Separate completed oracle-guided upper-bound budget-1 run. |
| `/Users/jaray/Documents/autoresearch/runs/replay_repair_3bench_coreai/results.jsonl` | CoreAI Freeform replay repair ablation rows. |
| `/Users/jaray/Documents/autoresearch/reports/data/replay_repair_3bench_coreai/results.jsonl` | Committed compact copy of CoreAI replay row-level data. |
| `/Users/jaray/Documents/autoresearch/reports/data/replay_repair_3bench_coreai/aggregate.json` | Committed aggregate for the CoreAI replay run. |
| `/Users/jaray/Documents/autoresearch/reports/replay_repair_coreai_freeform_results.md` | CoreAI-only replay repair report. |
| `/Users/jaray/Documents/autoresearch/reports/oracle_blind_evaluation_results.md` | Paper-facing oracle-blind primary result report. |
| `/Users/jaray/Documents/autoresearch/reports/budget_8_16_verification.md` | Budget-8/16 configs, partial probes, and trace-based plateau verification. |
| `/Users/jaray/Documents/autoresearch/reports/external_benchmark_integration.md` | SWE-bench, DS-1000, and MLAgentBench integration report. |
| `/Users/jaray/Documents/autoresearch/reports/official_runner_bridge.md` | Official SWE-bench/MLAgentBench runner bridge report. |
| `/Users/jaray/Documents/autoresearch/reports/official_swebench_real_results.md` | Real official SWE-bench Modal result report. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_3.yaml` | Budget-3 practical primary config. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_8.yaml` | Full practical matrix config for call budget 8. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_practical_matrix_budget_16.yaml` | Full practical matrix config for call budget 16. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_mini_workflow_budget_8.yaml` | Targeted MiniWorkflow verification config for call budget 8. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_mini_workflow_budget_16.yaml` | Targeted MiniWorkflow verification config for call budget 16. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_swebench_subset.yaml` | SWE-bench Lite/Verified subset config. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_ds1000_subset.yaml` | DS-1000 executable code-repair subset config. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_mlagentbench_subset.yaml` | MLAgentBench manifest adapter config. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_external_benchmarks_smoke.yaml` | Dummy-client smoke config across external benchmark adapters. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_replay_repair_3bench_coreai.yaml` | CoreAI replay repair config with 24 tasks and 5 repair-message policies. |
| `/Users/jaray/Documents/autoresearch/configs/experiment_repair_factor_ablation_budget_4.yaml` | Repair-factor ablation config for candidate retention, natural-language errors, targeted untyped repair, typed no-retain, and typed-repair+retain. |

## Bottom Line

The current evidence is enough to seed a workshop systems/evaluation paper, with one strong new primary result: on the completed Qwen2.5-Coder 14B practical lane, typed-repair+retain reaches 502/540 at budget 4 and beats `generic-retry` under lower total calls. The defensible claim is that VeriHarness provides an auditable way to test generation/acceptance separation, external gates, generic retry, and typed repair under controlled local-model conditions, and that typed repair can pay off sharply on verifiable workflow tasks when the model and budget are strong enough. The paper should not frame context bloat as proven by the practical matrix, and should not treat oracle-guided rows as operational evidence.
