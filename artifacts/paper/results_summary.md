# Results Summary

Primary practical result: Qwen2.5-Coder 14B, local Ollama, oracle-blind
evaluation over 540 rows per variant. Bootstrap confidence intervals are from
`veriharness.experiments.stats.bootstrap_ci`, seed 1, 200 resamples, alpha 0.05.

| Budget | Variant | Success, 95% bootstrap CI | Leaf calls | MiniWorkflow |
|---:|---|---:|---:|---:|
| 1 | H0 | 406/540 (75.2%, CI 71.5%-78.7%) | 540 | 0/90 |
| 1 | H3 | 420/540 (77.8%, CI 74.3%-81.1%) | 540 | 18/90 |
| 1 | generic-retry | 426/540 (78.9%, CI 75.6%-82.0%) | 540 | 18/90 |
| 1 | H4 | 423/540 (78.3%, CI 75.0%-81.7%) | 540 | 18/90 |
| 2 | H0 | 404/540 (74.8%, CI 71.1%-78.3%) | 540 | 0/90 |
| 2 | H3 | 419/540 (77.6%, CI 74.1%-80.9%) | 620 | 18/90 |
| 2 | generic-retry | 430/540 (79.6%, CI 76.3%-83.0%) | 619 | 18/90 |
| 2 | H4 | 422/540 (78.1%, CI 74.6%-81.7%) | 620 | 18/90 |
| 4 | H0 | 404/540 (74.8%, CI 71.1%-78.3%) | 540 | 0/90 |
| 4 | H3 | 418/540 (77.4%, CI 74.1%-80.6%) | 783 | 17/90 |
| 4 | generic-retry | 426/540 (78.9%, CI 75.4%-82.2%) | 772 | 17/90 |
| 4 | H4 | 502/540 (93.0%, CI 90.4%-95.2%) | 700 | 90/90 |

Interpretation:

- H4 does not beat generic retry at budgets 1 or 2.
- At budget 4, H4 beats generic retry by 76 successes and uses 72 fewer leaf
  calls.
- The paired budget-4 H4-vs-generic comparison is +14.1 percentage points with
  95% paired bootstrap CI +11.1 to +17.0 points and exact McNemar p=3.8e-20.
- The budget-4 gain is concentrated in verifiable workflow tasks.
- Oracle-guided upper-bound runs are separate from these primary rows.
- The practical matrix records no context-bloat proxy events, so context bloat
  remains diagnostic rather than a primary practical-matrix claim.

Feedback-driven additions:

- Added `natural-retry`, `retain+generic`, `targeted+untyped`, and
  `typed+no-retain` ablation variants.
- Added budget-3 primary config and launched multi-model replication for
  `qwen2.5-coder:14b`, `qwen2.5-coder:7b`, and `qwen2.5:7b`.
- Budget-3 `qwen2.5-coder:14b` completed: H4 solves 502/540 (93.0%, CI
  90.4%-95.2%) versus generic retry at 428/540 (79.3%, CI 75.9%-82.6%).
  Paired H4-vs-generic delta is +13.7 points, CI +10.9 to +16.7, exact
  McNemar p=1.4e-19.
- Added aggregate outputs for `per_seed_results.csv`, `paired_policy_tests.csv`,
  and `prompt_token_overhead.csv`.
- Fixed future leaf artifact paths to include benchmark and seed, preventing
  repeated public-benchmark ids from overwriting traces across seeds.

Failure taxonomy used in the report:

- constraint forgotten
- distractor adopted
- wrong own claim accepted
- schema invalid
- artifact missing
- missing evidence
- test failed
- premature done
- budget exhausted
