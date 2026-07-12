#!/usr/bin/env python3
"""Run the resumable reviewer-requested TextWorld and public-test campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from veriharness.core.orchestrator import Orchestrator
from veriharness.core.types import ExperimentConfig
from veriharness.experiments.aggregate import read_results

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
LOG = RUNS / "reviewer_extension_registry.jsonl"

MODELS: Dict[str, Dict[str, Any]] = {
    "qwen_coder_14b": {
        "client": "local",
        "provider": "ollama",
        "model_name": "qwen2.5-coder:14b",
        "parameter_count": 14_700_000_000,
        "parameter_count_label": "14.7B coder",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "max_output_tokens": 512,
        "timeout_seconds": 120,
    },
    "llama_8b": {
        "client": "local",
        "provider": "ollama",
        "model_name": "llama3.1:8b",
        "parameter_count": 8_000_000_000,
        "parameter_count_label": "8B",
        "endpoint": "http://localhost:11434/v1/chat/completions",
        "max_output_tokens": 512,
        "timeout_seconds": 120,
    },
}

TEXTWORLD_POLICIES = [
    "generic+diagnostics",
    "same-info-natural",
    "location-observed",
    "typed-fields",
    "typed-preserve",
    "typed-repair+retain",
]
CAUSAL_POLICIES = [
    "generic+diagnostics",
    "same-info-natural",
    "location-observed",
    "typed-fields",
]


def _config(
    experiment_id: str,
    benchmark: str,
    n_tasks: int,
    task_seed: int,
    policies: List[str],
    model_key: str,
    budget: int,
    *,
    temperature: float = 0.0,
    top_p: float | None = None,
    sampling_seed: int | None = None,
    role: str,
) -> Dict[str, Any]:
    model = dict(MODELS[model_key])
    model.update({"temperature": temperature, "top_p": top_p, "sampling_seed": sampling_seed})
    return {
        "experiment_id": experiment_id,
        "benchmarks": [{"name": benchmark, "n_tasks": n_tasks, "seeds": [task_seed]}],
        "variants": policies,
        "model": model,
        "evaluation": {"oracle_guided_acceptance": False, "result_role": role},
        "budget": {
            "max_retries": budget - 1,
            "veriharness_k": 2,
            "max_leaf_calls_per_task": budget,
            "max_wall_time_seconds": 172800,
        },
        "metadata": {
            "study": "reviewer_extension_v1",
            "task_subset_rule": "deterministic_rotation_by_seed",
            "textworld_expected_list_policy": "environment_order_first_12",
            "hidden_oracle_use": "posthoc_only",
        },
    }


def campaign() -> Iterable[Dict[str, Any]]:
    # Highest-value equal-budget comparison first.
    for model_key in MODELS:
        yield _config(
            f"reviewer_textworld_b4_{model_key}", "textworld", 50, 151,
            TEXTWORLD_POLICIES, model_key, 4, role="deterministic_primary",
        )

    # Separate software-repair scope check with one public assertion per task.
    for model_key in MODELS:
        yield _config(
            f"reviewer_humaneval_public_b4_{model_key}", "humaneval_public", 50, 1,
            CAUSAL_POLICIES, model_key, 4, role="visible_test_code_scope",
        )

    # Budget sensitivity around the primary budget-4 result.
    for budget in (2, 6, 8):
        for model_key in MODELS:
            yield _config(
                f"reviewer_textworld_b{budget}_{model_key}", "textworld", 50, 151,
                TEXTWORLD_POLICIES, model_key, budget, role="budget_sensitivity",
            )

    # Sampling robustness isolates raw diagnostics, information, and structure.
    for model_key in MODELS:
        for repeat, sampling_seed in enumerate((3101, 3102, 3103), start=1):
            yield _config(
                f"reviewer_textworld_sample_r{repeat}_{model_key}", "textworld", 50, 151,
                ["generic+diagnostics", "same-info-natural", "typed-fields"],
                model_key, 4, temperature=0.3, top_p=0.9,
                sampling_seed=sampling_seed, role="sampling_robustness",
            )


def _expected_rows(raw: Dict[str, Any]) -> int:
    return sum(item["n_tasks"] * len(item["seeds"]) for item in raw["benchmarks"]) * len(raw["variants"])


def _record(payload: Dict[str, Any]) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def run_one(raw: Dict[str, Any]) -> Path:
    config = ExperimentConfig.model_validate(raw)
    run_dir = RUNS / config.experiment_id
    expected = _expected_rows(raw)
    if run_dir.exists() and (run_dir / "config.yaml").exists():
        existing = len(read_results(run_dir)) if (run_dir / "results.jsonl").exists() else 0
        if existing >= expected:
            _record({"experiment_id": config.experiment_id, "status": "already_complete", "rows": existing})
            return run_dir
        summary = Orchestrator(config, raw_config=raw).resume(run_dir)
        _record({"experiment_id": config.experiment_id, "status": "resumed", **summary})
        return run_dir

    run_dir = Orchestrator(config, raw_config=raw).run()
    rows = len(read_results(run_dir))
    _record({"experiment_id": config.experiment_id, "status": "complete", "rows": rows, "run_dir": str(run_dir)})
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N campaign configs.")
    args = parser.parse_args()
    items = list(campaign())
    if args.limit > 0:
        items = items[: args.limit]
    for index, raw in enumerate(items, start=1):
        print(f"[{index}/{len(items)}] {raw['experiment_id']}", flush=True)
        run_one(raw)


if __name__ == "__main__":
    main()
