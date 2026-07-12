# Paper Evidence Baseline Matrix

Date: 2026-07-08

This table maps the requested paper evidence grid to the completed artifacts in
this repository. It separates completed model-performance evidence from probe
or bridge evidence.

Legend:

- `--`: no completed row-level model-performance run found.
- `probe`: small-N probe evidence; useful for feasibility, not a headline result.
- `replay`: replay-repair evidence; policies see frozen failed attempts rather
  than full first-attempt generation.
- `smoke`: adapter/bridge smoke evidence only; not model-performance evidence.

## Strategy Columns

| Column | Meaning in current harness |
|---|---|
| `self-accept` | Full/raw context with leaf self-acceptance; oracle used post-hoc. |
| `gated-resample` | State context with external gates; no failure-conditioned repair. |
| `generic-retry` | External gates plus generic retry feedback. |
| `generic+diagnostics / Reflexion` | Completed rows use `generic+diagnostics`, i.e. raw validation-message retry. Reflexion-style `natural-retry` is configured but not completed for this requested matrix. |
| `best-of-N gated` | Implemented as `best-of-n-gated`: state context plus external gates over multiple independent candidates, without repair feedback. |
| `LangGraph validator-retry` | Implemented as `langgraph-validator-retry`: a generate -> validate -> retry graph baseline with natural-language validation feedback. |
| `typed-repair+retain` | State context, external gates, candidate retention, typed failure-conditioned repair, and preserve-set instructions. |

## Completed Local Evidence: Qwen2.5-Coder 14B

Source: `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_4_local_ollama_qwen_coder_14b/results.jsonl`

Run status: oracle-blind primary matrix, budget 4, seeds 1-3. This is the
strongest current paper-facing result set.

| Benchmark | self-accept | gated-resample | generic-retry | generic+diagnostics / Reflexion | best-of-N gated | LangGraph validator-retry | typed-repair+retain |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoolQ | 40/60 | 37/60 | 42/60 | -- | -- | -- | 48/60 |
| SciQ | 57/60 | 57/60 | 57/60 | -- | -- | -- | 57/60 |
| ARC-Easy | 54/60 | 54/60 | 57/60 | -- | -- | -- | 54/60 |
| SQuAD | 60/60 | 60/60 | 60/60 | -- | -- | -- | 60/60 |
| GLUE SST-2 | 54/60 | 54/60 | 54/60 | -- | -- | -- | 54/60 |
| GLUE RTE | 59/60 | 59/60 | 59/60 | -- | -- | -- | 59/60 |
| GLUE MRPC | 53/60 | 53/60 | 53/60 | -- | -- | -- | 53/60 |
| TREC-QC | 27/30 | 27/30 | 27/30 | -- | -- | -- | 27/30 |
| MiniWorkflow | 0/90 | 17/90 | 17/90 | -- | -- | -- | 90/90 |
| DS-1000 subset | -- | -- | -- | -- | -- | -- | -- |
| **Total, excluding DS-1000** | **404/540** | **418/540** | **426/540** | -- | -- | -- | **502/540** |

## Completed Local Evidence: Qwen2.5 7B

Source: `/Users/jaray/Documents/autoresearch/runs/practical_matrix_budget_3_local_ollama_qwen/results.jsonl`

Run status: oracle-blind replication matrix, budget 3, seeds 1-3. This is useful
for model-family robustness, but the budget does not exactly match the 14B
budget-4 primary result.

| Benchmark | self-accept | gated-resample | generic-retry | generic+diagnostics / Reflexion | best-of-N gated | LangGraph validator-retry | typed-repair+retain |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoolQ | 0/60 | 0/60 | 27/60 | -- | -- | -- | 33/60 |
| SciQ | 54/60 | 58/60 | 57/60 | -- | -- | -- | 55/60 |
| ARC-Easy | 54/60 | 54/60 | 54/60 | -- | -- | -- | 54/60 |
| SQuAD | 54/60 | 54/60 | 54/60 | -- | -- | -- | 54/60 |
| GLUE SST-2 | 51/60 | 50/60 | 56/60 | -- | -- | -- | 56/60 |
| GLUE RTE | 41/60 | 41/60 | 41/60 | -- | -- | -- | 41/60 |
| GLUE MRPC | 41/60 | 41/60 | 41/60 | -- | -- | -- | 41/60 |
| TREC-QC | 27/30 | 27/30 | 27/30 | -- | -- | -- | 27/30 |
| MiniWorkflow | 18/90 | 90/90 | 74/90 | -- | -- | -- | 90/90 |
| DS-1000 subset | -- | -- | -- | -- | -- | -- | -- |
| **Total, excluding DS-1000** | **340/540** | **415/540** | **431/540** | -- | -- | -- | **451/540** |

## CoreAI Freeform Evidence

Sources:

- self-accept/gated-resample/typed-repair+retain probes:
  - `/Users/jaray/Documents/autoresearch/runs/coreai_suitable_probe/results.jsonl`
  - `/Users/jaray/Documents/autoresearch/runs/coreai_more_suitable_probe/results.jsonl`
- Replay-repair rows:
  - `/Users/jaray/Documents/autoresearch/reports/data/replay_repair_3bench_coreai/results.jsonl`

Run status: mixed small-N probes plus replay-repair diagnostics. These rows are
useful for Mac-local feasibility and failure-mode evidence, but they are not a
single full matrix.

| Benchmark | self-accept | gated-resample | generic-retry | generic+diagnostics / Reflexion | best-of-N gated | LangGraph validator-retry | typed-repair+retain |
|---|---:|---:|---:|---:|---:|---:|---:|
| BoolQ | 2/5 probe | 3/5 probe | 5/8 replay | 7/8 replay | -- | -- | 3/5 probe |
| SciQ | 1/3 probe | 2/3 probe | 4/8 replay | 6/8 replay | -- | -- | 2/3 probe |
| ARC-Easy | 1/3 probe | 3/3 probe | -- | -- | -- | -- | 3/3 probe |
| SQuAD | 4/5 probe | 4/5 probe | -- | -- | -- | -- | 4/5 probe |
| GLUE SST-2 | 3/3 probe | 3/3 probe | -- | -- | -- | -- | 3/3 probe |
| GLUE RTE | 1/3 probe | 2/3 probe | -- | -- | -- | -- | 2/3 probe |
| GLUE MRPC | 2/3 probe | 2/3 probe | -- | -- | -- | -- | 2/3 probe |
| TREC-QC | 0/3 probe | 2/3 probe | -- | -- | -- | -- | 2/3 probe |
| MiniWorkflow | 0/5 probe | 5/5 probe | 8/8 replay | 6/8 replay | -- | -- | 5/5 probe |
| DS-1000 subset | -- | -- | -- | -- | -- | -- | -- |

CoreAI replay also contains typed repair policy rows that are not full typed-repair+retain:

| Benchmark | typed-label-only | typed-fields | typed-preserve |
|---|---:|---:|---:|
| BoolQ | 7/8 | 7/8 | 7/8 |
| SciQ | 4/8 | 5/8 | 8/8 |
| MiniWorkflow | 8/8 | 6/8 | 0/8 |
| **Total** | **19/24** | **18/24** | **15/24** |

## DS-1000 Status

Configured local DS-1000 probe:

- `/Users/jaray/Documents/autoresearch/configs/experiment_ds1000_subset.yaml`

Completed evidence:

| Evidence type | Model | gated-resample | typed-repair+retain | Paper status |
|---|---|---:|---:|---|
| Adapter smoke | dummy | 1/1 | 1/1 | Validates adapter/gate path only; not model-performance evidence. |

Missing model-performance rows:

| Model | Needed strategies |
|---|---|
| qwen2.5-coder:14b | self-accept, gated-resample, generic-retry, generic+diagnostics or Reflexion, best-of-N gated, LangGraph validator-retry, typed-repair+retain |
| qwen2.5:7b or llama3.1:8b | self-accept, gated-resample, generic-retry, generic+diagnostics or Reflexion, best-of-N gated, LangGraph validator-retry, typed-repair+retain |
| CoreAI Freeform | self-accept, gated-resample, generic-retry, generic+diagnostics or Reflexion, best-of-N gated, LangGraph validator-retry, typed-repair+retain |

## Gaps To Fill Before Claiming Full Baseline Coverage

| Gap | Why it matters | Current repo status |
|---|---|---|
| `generic+diagnostics` on the primary Qwen matrices | Tests whether raw gate diagnostics explain typed-repair+retain gains. | Implemented variant; not completed in primary Qwen practical matrix. |
| Reflexion-style `natural-retry` on the primary Qwen matrices | Gives a recognizable verbal self-repair baseline. | Configured in repair-factor ablation; not completed in requested matrix. |
| `best-of-N gated` | Controls for typed-repair+retain gaining from more samples/candidate selection rather than typed repair. | Implemented and configured; completed model-performance rows still pending. |
| LangGraph validator-retry | Gives a graph-style code-as-harness baseline. | Implemented as `langgraph-validator-retry` and configured; completed model-performance rows still pending. |
| DS-1000 model-performance rows | Adds executable code-repair evidence beyond harness-generated NLP/workflow tasks. | Adapter smoke only; local executable oracle exists. |
| Equal-budget qwen2.5:7b or llama3.1:8b replication | Makes model-family comparison cleaner. | qwen2.5:7b completed at budget 3; llama3.1:8b has budget-1 rows only. |

Runnable completion configs:

- `/Users/jaray/Documents/autoresearch/configs/experiment_paper_baseline_completion_budget_4.yaml`
- `/Users/jaray/Documents/autoresearch/configs/experiment_paper_baseline_completion_smoke.yaml`

The full budget-4 completion config is 4,480 rows per model: 560 tasks times
8 strategies. For three models, the requested complete run is 13,440 rows.
It uses oracle-blind primary scoring; DS-1000 execution is therefore post-hoc
scoring rather than online repair feedback in that config.

Validation smoke run:

- `/Users/jaray/Documents/autoresearch/runs/paper_baseline_completion_smoke/results.jsonl`
- 48 dummy-client rows over BoolQ, SciQ, and MiniWorkflow.
- All requested strategy names executed through the normal CLI:
  `self-accept`, `gated-resample`, `generic-retry`, `generic+diagnostics`, `natural-retry`,
  `best-of-n-gated`, `langgraph-validator-retry`, and `typed-repair+retain`.
- This validates harness wiring only; it is not paper model-performance evidence.

## Recommended Paper-Ready Completion Matrix

The next complete matrix should run the requested benchmarks with these
strategy groups under equal call budget 4:

| Model | Benchmarks | Strategies |
|---|---|---|
| qwen2.5-coder:14b | Requested NLP/workflow set plus DS-1000 subset | self-accept, gated-resample, generic-retry, generic+diagnostics, natural-retry, best-of-N gated, LangGraph validator-retry, typed-repair+retain |
| qwen2.5:7b or llama3.1:8b | Same | Same |
| CoreAI Freeform | Same, with smaller DS-1000 subset if context limits bind | Same |

Until those missing cells are filled, the strongest defensible claim remains:
typed-repair+retain beats gated-resample and generic retry on the completed qwen2.5-coder:14b practical
matrix, with the gain concentrated on verifiable workflow tasks. The requested
real-baseline evidence is partially present, but not complete.
