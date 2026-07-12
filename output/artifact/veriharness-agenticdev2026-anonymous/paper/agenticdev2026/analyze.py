#!/usr/bin/env python3
"""Recompute the AgenticDev paper statistics from row-level results."""

from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUN = ROOT / "runs" / "textworld_focused_ablation_budget_4_local_ollama_qwen_coder_14b"
VARIANTS = [
    "generic+diagnostics",
    "typed-fields",
    "typed-preserve",
    "typed-repair+retain",
]
PAIRS = [
    ("generic+diagnostics", "typed-fields"),
    ("typed-fields", "typed-preserve"),
    ("typed-preserve", "typed-repair+retain"),
    ("generic+diagnostics", "typed-repair+retain"),
]


def bootstrap_delta(deltas: list[int], draws: int = 10_000) -> tuple[float, float]:
    rng = random.Random(1)
    samples = sorted(
        sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
        for _ in range(draws)
    )
    return samples[int(0.025 * (draws - 1))], samples[int(0.975 * (draws - 1))]


def mcnemar_exact(baseline_only: int, treatment_only: int) -> float:
    discordant = baseline_only + treatment_only
    if not discordant:
        return 1.0
    tail = min(baseline_only, treatment_only)
    probability = sum(math.comb(discordant, k) for k in range(tail + 1)) / (2**discordant)
    return min(1.0, 2 * probability)


def main() -> None:
    run = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_RUN
    rows = [json.loads(line) for line in (run / "results.jsonl").read_text().splitlines()]
    assert len(rows) == 200
    by_variant: dict[str, list[dict]] = defaultdict(list)
    by_instance = {}
    for row in rows:
        by_variant[row["variant"]].append(row)
        by_instance[(row["task_id"], row["variant"])] = row

    tasks = sorted({row["task_id"] for row in rows})
    summary = {}
    for variant in VARIANTS:
        group = by_variant[variant]
        failures = Counter(reason for row in group for reason in row["failure_reasons"])
        transcripts = list((run / "artifacts" / "leaves" / variant).rglob("transcript.txt"))
        summary[variant] = {
            "success": sum(bool(row["success"]) for row in group),
            "n": len(group),
            "calls": sum(int(row["num_leaf_calls"]) for row in group),
            "prompt_word_proxy": sum(len(path.read_text(errors="replace").split()) for path in transcripts),
            "action_invalid": failures["action_invalid"],
        }

    paired = {}
    for baseline, treatment in PAIRS:
        deltas = [
            int(by_instance[(task, treatment)]["success"])
            - int(by_instance[(task, baseline)]["success"])
            for task in tasks
        ]
        treatment_only = sum(delta == 1 for delta in deltas)
        baseline_only = sum(delta == -1 for delta in deltas)
        paired[f"{treatment}_vs_{baseline}"] = {
            "delta": sum(deltas) / len(deltas),
            "ci": bootstrap_delta(deltas),
            "treatment_only": treatment_only,
            "baseline_only": baseline_only,
            "mcnemar_exact_p": mcnemar_exact(baseline_only, treatment_only),
        }

    print(json.dumps({"summary": summary, "paired": paired}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
