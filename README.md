# VeriHarness

VeriHarness is a research-grade prototype for testing verifiable agent harnesses for
long-horizon LLM automation.

It is not a general agent framework. It is a controlled experimental harness for two
claims:

1. **Context overload**: long-running agents degrade when raw execution history buries
   active constraints among stale traces, failed attempts, and distractors.
2. **Self-evaluation bias**: agents prematurely accept flawed work when the same model
   or leaf evaluates its own output; external gates should reduce wrong acceptance.

## Architecture

```text
                    Task
                     |
              Python Orchestrator
        +------------+-------------+
        |            |             |
   State Store   Context Pack   Gate Stack
        |            |             |
        +------------+-------------+
                     |
                 LLM Leaf
                     |
              Structured Output
                     |
              External Acceptance
```

## Causal Ablation

```text
H0: full trace + self accept
H1: summary + self accept
H2: state context + self accept
H3: state context + external gates
H4: state context + external gates + VeriHarness
```

The workshop paper matrix also adds `generic-retry`, an equal-compute baseline
with state context, external gates, and untyped retry feedback.

## Practical Paper Matrix

The paper-quality protocol is documented in
`reports/practical_matrix_protocol.md`. It uses:

- 150 verifiable leaf tasks and 30 workflow tasks per seed,
- seeds 1, 2, and 3,
- local models from distinct families,
- H0, H3, `generic-retry`, and H4,
- call budgets 1, 2, and 4,
- oracle-blind primary acceptance,
- oracle-guided runs reported separately as upper bounds.

Primary configs:

```text
configs/experiment_practical_matrix_budget_1.yaml
configs/experiment_practical_matrix_budget_2.yaml
configs/experiment_practical_matrix_budget_4.yaml
```

Example local run:

```bash
python3 -m veriharness.cli.main run-model-matrix \
  --config configs/experiment_practical_matrix_budget_1.yaml \
  --models-config configs/models.yaml \
  --models local_ollama_llama,local_ollama_qwen_coder_14b,local_ollama_gpt_oss_20b
```

## Quickstart

```bash
make test
make lint
make typecheck
make smoke
```

The smoke run is deterministic and uses `DummyClient`; no hosted model key is needed.

```bash
python3 -m veriharness.cli.main run --config configs/experiment_smoke.yaml
python3 -m veriharness.cli.main inspect-run --run-dir runs/latest
python3 -m veriharness.cli.main aggregate --run-dir runs/latest
python3 -m veriharness.cli.main plot --run-dir runs/latest
```

Workshop-oriented result bundles can be regenerated from one or more run directories:

```bash
python3 -m veriharness.cli.main compile-workshop \
  --run-dirs runs/model_a,runs/model_b \
  --out-dir runs/workshop_compiled \
  --expected-rows 54
```

This writes model, variant, benchmark, baseline-comparison, and failure-example
tables with bootstrap confidence intervals where applicable.

## Benchmarks

- `context_trace`: synthetic traces where an invariant appears early, middle, or late
  among distractors.
- `provenance_bias`: the same wrong claim is reused under different provenance labels.
- `mini_workflow`: cheap realistic tasks with deterministic checks.

Every benchmark task has an oracle.

## Outputs

Each experiment writes:

```text
runs/<experiment_id>/
  config.yaml
  git_commit.txt
  environment.json
  results.jsonl
  events.jsonl
  aggregate.json
  leaderboard.csv
  artifacts/
```

Each leaf attempt writes:

```text
context_pack.md
transcript.txt
leaf_output.json
gate_results.json
event_log.jsonl
metadata.json
```

## Metrics

- `success_rate`
- `constraint_violation_rate`
- `premature_stop_rate`
- `wrong_claim_acceptance_rate`
- `self_evaluation_bias_gap`
- `context_overload_slope`
- `tokens_per_success`
- `retries_per_success`

Tables are written under `artifacts/tables/`; figures are written under
`artifacts/figures/`.

## Known Limitations

The default local client is deterministic and meant for harness validation, not model
quality measurement. Hosted and local model clients are behind the same interface but
are intentionally optional. The current mini workflow benchmark uses deterministic
artifact and field checks rather than spawning full nested development environments.
