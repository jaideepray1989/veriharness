# E5 deep sweep — temperature × VeriHarness ablation (qwen2.5-coder:14b)

Deep re-run of the E5 fair-baseline ablation at **budget 4**, **seeds [1,2,3]**, across
three decoder temperatures. Produced on a local OpenAI-compatible endpoint (Ollama)
run with `--concurrency 8`. Greedy-decode (temperature 0.0) output was verified
**byte-identical to the sequential single-request baseline**, so these results are
comparable to the prior local probe.

- **Model:** `qwen2.5-coder:14b` (Q4_K_M, 14.8B)
- **Tasks:** mini_workflow (n=30/seed) + boolq (n=10/seed) → 120 leaves/variant/temp
- **Rows:** 480 per temp (4 variants × 120), all runs exited cleanly

## Variants
| id | context | acceptance |
|----|---------|------------|
| generic-retry | naive resample baseline | none |
| H0 | full trace | self-accept |
| H3 | state context | external gates |
| H4 | state context | external gates **+ VeriHarness typed repair** |

## Headline: success rate by variant × temperature (pooled)
| variant | T=0.0 | T=0.7 | T=1.0 |
|---|---|---|---|
| generic-retry | 0.0% | 32.5% | 32.5% |
| H0 | 16.7% | 19.2% | 15.8% |
| H3 | 27.5% | 41.7% | 44.2% |
| **H4** | **67.5%** | **95.0%** | **93.3%** |

## The pooled number hides two things

### 1. H4's advantage is concentrated in multi-step tasks
`mini_workflow` (multi-step, where verification matters):
| variant | T=0.0 | T=0.7 | T=1.0 |
|---|---|---|---|
| H0 | 0% | 0% | 0% |
| generic-retry | 0% | 18% | 20% |
| H3 | 19% | 30% | 34% |
| **H4** | 63% | **100%** | **99%** |

`boolq` (single-step): all self/gated variants cluster 63–80%; H4 leads only modestly.
Self-accept (H0) **never** completes a multi-step workflow (0% at every temperature) —
this is the self-bias failure the harness targets.

### 2. Temperature 0.0 is not a neutral baseline for repair-based variants
H4 mini_workflow success by seed:
| seed | T=0.0 | T=0.7 | T=1.0 |
|---|---|---|---|
| 1 | **0/30** | 30/30 | 29/30 |
| 2 | 27/30 | 30/30 | 30/30 |
| 3 | 30/30 | 30/30 | 30/30 |

At T=0.0 the greedy decoder makes every retry an identical draw, so a wrong first
attempt can never be repaired — success collapses to "did the single deterministic
output pass?" and becomes wildly seed-dependent (seed 1 = 0/30). `generic-retry = 0%`
at T=0.0 is the same mechanism. **Once T≥0.7 supplies sampling diversity, H4 is fully
seed-robust (29–30/30 across all seeds).** This confirms finding **F1** and
sharpens **F2** (mini_workflow template memorization): report
per-seed, never pooled, and treat T≥0.7 as the fair comparison point for repair loops.

### Findings F1 & F2 (verbatim, from the repo audit)

> **F1 — The resampling baseline runs at temperature 0.0.** `veriharness/llm/local_client.py` defaults to `temperature=0.0`, and every local model entry in `configs/models.yaml` that sets a temperature sets `0.0`. With a deterministic decoder, gate-resample (H3) retries are near-identical draws, which mechanically explains why H3 and generic retry are flat from budget 1 to 4 in Figure 2. This is the single most important fix: the paper's baselines may be handicapped, and the typed-repair delta could shrink at temperature 0.7–1.0. **Experiment E5 below is now Tier 1, not Tier 2.**

> **F2 — MiniWorkflow is 5 templates, not 90 tasks.** `veriharness/benchmarks/mini_workflow.py` defines exactly five `(name, instruction, expected)` tuples and cycles them (`WORKFLOWS[i % len(WORKFLOWS)]`) to generate 30 tasks per seed. The 90 workflow "tasks" are 5 templates × 18 instantiations, and the hidden oracle is substring matching (`expected_substring`, `forbidden_substring`) plus an artifact-presence check. The 90/90 result is therefore 5/5 templates solved, repeated. This makes the public-benchmark validation (E3) and a MiniWorkflow diversity expansion (E3b) far more urgent than the paper's limitations section suggests.

## Integrity — the critical safety check
`wrong_claim_accepted` across all 360 rows per variant:
```
generic-retry 0/360 · H0 0/360 · H3 0/360 · H4 0/360   (0.0% each)
```
**No variant ever accepted a wrong claim.** H4's gains are real, not gate-gaming —
it raises success without trading away correctness (repo invariant: a leaf never
decides final acceptance for a gated variant).

## Files
- `temp_{0.0,0.7,1.0}/` — full per-temp snapshots (leaderboard, aggregate, per-seed,
  paired policy tests, failure modes, raw `results.jsonl`, config, environment)
- `success_by_benchmark_variant_temp.csv` — machine-readable version of the tables above
- `h4_mini_workflow_seed_robustness.csv` — per-seed × temp breakdown
- `integrity_wrong_claim_accepted.csv` — wrong-claim-accepted rates
