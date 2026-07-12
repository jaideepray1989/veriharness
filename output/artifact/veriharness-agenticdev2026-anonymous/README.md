# VeriHarness Anonymous Artifact

This artifact reproduces the 880-row study reported in the anonymous
AgenticDev paper. It contains the harness source, exact row-level results,
per-call traces, fixed task assets, run configurations, and analysis outputs.

## Dataset

- Primary TextWorld: 50 games x 4 policies x 2 models = 400 rows.
- Public-test HumanEval scope check: 15 tasks x 4 policies x 2 models = 120 rows.
- Budget sensitivity: 180 additional rows at budgets 2, 6, and 8; budget-4
  rows are reused from the primary experiment.
- Sampled decoding: 20 games x 3 policies x 3 inference seeds = 180 rows.
- Total: 880 rows and 2,652 realized LLM leaf calls.

The original transient serving-error row is retained separately under its run
directory and is not part of `results.jsonl`. Its identical rerun is included
in the 880-row dataset.

## Recompute

From the artifact root:

```bash
python3 paper/agenticdev2026/analyze_modal_paper900.py
```

The script validates all row counts and pairing keys, rejects infrastructure
errors, and writes the paper tables to `reports/paper900/`. It uses only the
Python standard library.

## Smoke Tests

```bash
cd source_snapshot
python3 -m pip install -e .
pytest tests -q --import-mode=importlib
```

Smoke tests use deterministic clients and do not require hosted credentials.

## Full Inference Replication

The saved data is sufficient to reproduce every reported statistic without a
model endpoint. Re-running inference additionally requires:

- TextWorld 1.7.0;
- vLLM-compatible Qwen2.5-Coder-14B-Instruct-AWQ and
  Llama-3.1-8B-Instruct-AWQ-INT4 endpoints;
- `VERIHARNESS_MODAL_WORKSPACE` or equivalent endpoint configuration; and
- an NVIDIA L4 for Qwen and T4 for Llama, or documented substitute hardware.

The original evaluation used greedy decoding for primary, budget, and code
lanes. The sampling lane used temperature 0.3, top-p 0.9, and inference seeds
3101, 3102, and 3103.

## Layout

- `paper/agenticdev2026/`: manuscript source and deterministic analysis.
- `reports/paper900/`: generated JSON, CSV tables, and inclusion report.
- `runs/`: exact run directories and leaf traces.
- `source_snapshot/`: harness source, tests, configs, and launch scripts.
- `data/benchmarks/`: fixed TextWorld assets and HumanEval source data.
