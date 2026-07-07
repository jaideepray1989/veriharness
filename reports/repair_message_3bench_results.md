# Repair Message Ablation: 3-Benchmark Quick Run

Date: 2026-07-07

Purpose: compare five repair-message policies under the same call budget on three benchmarks.

Benchmarks:
- BoolQ: yes/no reading comprehension.
- SciQ: multiple-choice science QA.
- MiniWorkflow: small artifact/evidence workflow tasks.

Policies:
- `generic-retry`: generic retry only.
- `generic+diagnostics`: generic retry plus raw validation messages.
- `typed-label-only`: typed failure label only.
- `typed-fields`: typed failure label plus `location`, `expected`, and `observed`.
- `typed-preserve`: full typed repair plus preserve-set instructions.

Configuration:
- 2 tasks per benchmark, 3 benchmarks, 5 variants: 30 rows per model.
- Oracle-guided validation, because this ablation tests repair-feedback visibility.
- Call budget: 4 leaf calls per task, max 3 retries.
- Candidate retention disabled for all five policies to isolate repair prompt content.

## Runs

| Run | Model | Path | Rows |
|---|---|---:|---:|
| Quick local | Ollama `qwen2.5:3b` | `runs/repair_message_3bench_quick` | 30 |
| CoreAI replication | `SystemLanguageModel.default` freeform | `runs/repair_message_3bench_quick_coreai_freeform` | 30 |

An initial larger run with `qwen2.5-coder:7b` was stopped after 2 rows because it was too slow for an interactive pass. Its partial data remains in `runs/repair_message_3bench`.

## Overall Results

### Ollama Qwen 3B

| Policy | Success | Calls | Retries | Premature Stops |
|---|---:|---:|---:|---:|
| `generic-retry` | 0/6 | 24 | 18 | 2 |
| `generic+diagnostics` | 1/6 | 22 | 16 | 1 |
| `typed-label-only` | 0/6 | 24 | 18 | 0 |
| `typed-fields` | 0/6 | 24 | 18 | 0 |
| `typed-preserve` | 0/6 | 24 | 18 | 0 |

Qwen 3B was brittle under typed prompts. The only solved row came from `generic+diagnostics` on BoolQ. Typed variants often collapsed into empty/client-error outputs, so this run mainly shows a capability threshold and prompt-complexity failure.

### CoreAI Freeform

| Policy | Success | Calls | Retries | Premature Stops |
|---|---:|---:|---:|---:|
| `generic-retry` | 4/6 | 14 | 8 | 2 |
| `generic+diagnostics` | 3/6 | 16 | 10 | 2 |
| `typed-label-only` | 4/6 | 15 | 9 | 2 |
| `typed-fields` | 5/6 | 13 | 7 | 1 |
| `typed-preserve` | 5/6 | 14 | 8 | 0 |

CoreAI shows the intended ladder more clearly: typed fields improve over typed labels by +1/6, and typed preserve matches typed fields while eliminating premature stops in this small sample.

## By Benchmark

### Ollama Qwen 3B

| Benchmark | generic | diagnostics | label-only | fields | preserve |
|---|---:|---:|---:|---:|---:|
| BoolQ | 0/2 | 1/2 | 0/2 | 0/2 | 0/2 |
| MiniWorkflow | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |
| SciQ | 0/2 | 0/2 | 0/2 | 0/2 | 0/2 |

### CoreAI Freeform

| Benchmark | generic | diagnostics | label-only | fields | preserve |
|---|---:|---:|---:|---:|---:|
| BoolQ | 1/2 | 1/2 | 1/2 | 1/2 | 1/2 |
| MiniWorkflow | 2/2 | 0/2 | 1/2 | 2/2 | 2/2 |
| SciQ | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |

## Paired Deltas: CoreAI

| Comparison | Delta | Treatment-only | Baseline-only |
|---|---:|---:|---:|
| `generic+diagnostics` vs `generic-retry` | -1/6 | 1 | 2 |
| `typed-label-only` vs `generic+diagnostics` | +1/6 | 1 | 0 |
| `typed-fields` vs `typed-label-only` | +1/6 | 1 | 0 |
| `typed-preserve` vs `typed-fields` | 0/6 | 0 | 0 |
| `typed-preserve` vs `generic-retry` | +1/6 | 1 | 0 |

The sample is intentionally tiny, so these are directional diagnostics rather than statistical claims.

## Prompt Cost

CoreAI average retry prompt tokens:
- `generic-retry`: 582.6
- `generic+diagnostics`: 587.6
- `typed-label-only`: 538.3
- `typed-fields`: 576.4
- `typed-preserve`: 870.3

Typed preserve adds substantial prompt overhead: +287.6 retry tokens versus generic retry and +293.8 versus typed fields in this run.

## Interpretation

The CoreAI run supports two narrow claims:
- Raw diagnostics are not automatically better than generic retry; they helped SciQ but hurt MiniWorkflow.
- Typed `location/expected/observed` fields are more useful than typed labels alone on workflow repair.

The Qwen 3B run supports a capability-threshold caveat:
- A smaller model may fail to follow typed repair prompts at all, turning richer feedback into malformed or empty outputs.

The next publishable run should scale this exact ladder to more tasks and at least one stronger local model.
