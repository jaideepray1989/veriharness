#!/usr/bin/env python3
"""Run the reduced 880-row paper matrix with row- and block-level checkpoints."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml

from run_reviewer_extension import CAUSAL_POLICIES, MODELS, RUNS, _config, run_one

ROOT = Path(__file__).resolve().parents[1]
STATE = RUNS / "paper900_campaign_state.json"
MANIFEST = RUNS / "paper900_manifest.json"


def campaign() -> Iterable[Dict[str, Any]]:
    # Claim 1: information-matched, paired causal comparison at the main budget.
    for model_key in MODELS:
        yield _config(
            f"reviewer_textworld_b4_{model_key}", "textworld", 50, 151,
            CAUSAL_POLICIES, model_key, 4, role="paper900_primary",
        )

    # Scope check: public unit-test diagnostics with hidden official tests post hoc.
    for model_key in MODELS:
        yield _config(
            f"paper900_humaneval_public_b4_{model_key}", "humaneval_public", 15, 1,
            CAUSAL_POLICIES, model_key, 4, role="paper900_code_scope",
        )

    # Reviewer-requested budget sensitivity, focused on raw vs typed repair.
    for budget in (2, 6, 8):
        for model_key in MODELS:
            yield _config(
                f"paper900_textworld_b{budget}_{model_key}", "textworld", 15, 151,
                ["generic+diagnostics", "typed-fields"], model_key, budget,
                role="paper900_budget_sensitivity",
            )

    # Three seeded sampled repeats on the coder model: raw, same-info prose, typed.
    for repeat, sampling_seed in enumerate((3101, 3102, 3103), start=1):
        yield _config(
            f"paper900_textworld_sample_r{repeat}_qwen_coder_14b", "textworld", 20, 151,
            ["generic+diagnostics", "same-info-natural", "typed-fields"],
            "qwen_coder_14b", 4, temperature=0.3, top_p=0.9,
            sampling_seed=sampling_seed, role="paper900_sampling_robustness",
        )


def expected_rows(raw: Dict[str, Any]) -> int:
    tasks = sum(item["n_tasks"] * len(item["seeds"]) for item in raw["benchmarks"])
    return tasks * len(raw["variants"])


def checkpoint(items: list[Dict[str, Any]], active_index: int) -> None:
    blocks = []
    total_rows = 0
    total_expected = 0
    for raw in items:
        path = RUNS / raw["experiment_id"] / "results.jsonl"
        rows = sum(1 for _ in path.open()) if path.exists() else 0
        expected = expected_rows(raw)
        total_rows += min(rows, expected)
        total_expected += expected
        blocks.append({"experiment_id": raw["experiment_id"], "rows": rows, "expected": expected})
    STATE.write_text(
        json.dumps(
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "active_index": active_index,
                "rows": total_rows,
                "expected_rows": total_expected,
                "blocks": blocks,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def prepare_reused_primary(raw: Dict[str, Any]) -> None:
    run_dir = RUNS / raw["experiment_id"]
    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        return
    current = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if current.get("variants") == raw["variants"]:
        return
    backup = run_dir / "config.pre-paper900.yaml"
    if not backup.exists():
        backup.write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def main() -> None:
    items = list(campaign())
    MANIFEST.write_text(
        json.dumps(
            {
                "campaign": "paper900",
                "actual_rows": sum(expected_rows(raw) for raw in items),
                "design": "400 primary + 120 code + 180 budget + 180 sampling",
                "checkpointing": "each result row plus campaign state after every block",
                "experiments": [raw["experiment_id"] for raw in items],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    prepare_reused_primary(items[0])
    checkpoint(items, 0)
    for index, raw in enumerate(items, start=1):
        print(f"[{index}/{len(items)}] {raw['experiment_id']}", flush=True)
        run_one(raw)
        checkpoint(items, index)


if __name__ == "__main__":
    main()
