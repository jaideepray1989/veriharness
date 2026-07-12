from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List

from veriharness.core.types import TaskSpec

DEFAULT_CACHE_ROOT = Path("data/benchmarks/textworld")
PREREGISTERED_SEEDS = tuple(range(20_260_901, 20_261_101))
BRIDGE_PATH = Path(__file__).with_name("textworld_bridge.py")


def generate_textworld_tasks(
    n_tasks: int = 200,
    seed: int = 1,
    cache_root: Path = DEFAULT_CACHE_ROOT,
) -> List[TaskSpec]:
    if n_tasks > len(PREREGISTERED_SEEDS):
        raise ValueError(f"TextWorld supports at most {len(PREREGISTERED_SEEDS)} preregistered games.")
    selected = _select_seeds(n_tasks, seed)
    tasks: List[TaskSpec] = []
    for selection_index, game_seed in enumerate(selected):
        game_path = Path(cache_root) / "games" / f"textworld-{game_seed}.z8"
        descriptor = _load_or_generate_descriptor(
            Path(cache_root),
            game_path,
            game_seed,
        )
        task_id = f"textworld-{game_seed}"
        max_steps = 4
        tasks.append(
            TaskSpec(
                task_id=task_id,
                family="textworld",
                description="Complete the visible TextWorld objective with a bounded command plan.",
                input_payload={
                    "objective": descriptor["objective"],
                    "description": descriptor["description"],
                    "inventory": descriptor["inventory"],
                    "max_steps": max_steps,
                    "game_seed": game_seed,
                },
                hidden_oracle_payload={
                    "oracle_type": "textworld",
                    "game_path": descriptor["game_path"],
                    "max_steps": max_steps,
                    "required_artifacts": ["action_plan.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=[
                    "Return a JSON command plan with at most four TextWorld commands.",
                    "The local TextWorld environment reaches a terminal win state.",
                ],
                metadata={
                    "benchmark": "textworld",
                    "seed": seed,
                    "game_seed": game_seed,
                    "selection_index": selection_index,
                    "seed_manifest": "textworld-preregistered-v1",
                    "world_size": 3,
                    "object_count": 4,
                    "quest_length": 2,
                },
            )
        )
    return tasks


def _load_or_generate_descriptor(cache_root: Path, game_path: Path, game_seed: int) -> Dict[str, Any]:
    descriptor_path = Path(cache_root) / "metadata" / f"textworld-{game_seed}.json"
    if descriptor_path.exists():
        return json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor = _bridge(
        "generate",
        {
            "game_path": str(game_path),
            "game_seed": game_seed,
            "world_size": 3,
            "object_count": 4,
            "quest_length": 2,
        },
        timeout=90,
    )
    descriptor_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor_path.write_text(json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return descriptor


def evaluate_textworld_plan(task: TaskSpec, commands: Iterable[str]) -> Dict[str, Any]:
    return _evaluate_cached(
        str(task.hidden_oracle_payload.get("game_path", "")),
        tuple(str(command) for command in commands),
        int(task.hidden_oracle_payload.get("max_steps", 4)),
    )


@lru_cache(maxsize=16_384)
def _evaluate_cached(game_path: str, commands: tuple[str, ...], max_steps: int) -> Dict[str, Any]:
    return _bridge(
        "evaluate",
        {
            "game_path": game_path,
            "commands": list(commands),
            "max_steps": max_steps,
        },
        timeout=30,
    )


def _select_seeds(n_tasks: int, experiment_seed: int) -> tuple[int, ...]:
    offset = (max(experiment_seed, 1) - 1) % len(PREREGISTERED_SEEDS)
    rotated = PREREGISTERED_SEEDS[offset:] + PREREGISTERED_SEEDS[:offset]
    return tuple(rotated[:n_tasks])


def _bridge(operation: str, payload: Dict[str, Any], *, timeout: int) -> Dict[str, Any]:
    python = Path(os.environ.get("VERIHARNESS_TEXTWORLD_PYTHON", ".textworld-venv/bin/python"))
    if not python.exists():
        raise RuntimeError(
            "TextWorld bridge is unavailable. Set VERIHARNESS_TEXTWORLD_PYTHON to a Python environment with textworld installed."
        )
    completed = subprocess.run(
        [str(python), str(BRIDGE_PATH), "--operation", operation],
        input=json.dumps(payload),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"TextWorld bridge failed: {completed.stderr.strip()[-1000:]}")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"TextWorld bridge returned invalid JSON: {completed.stdout[:500]}") from exc
