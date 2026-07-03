from __future__ import annotations

import gzip
import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from veriharness.core.types import TaskSpec

HUMANEVAL_URL = "https://raw.githubusercontent.com/openai/human-eval/master/data/HumanEval.jsonl.gz"
DEFAULT_CACHE_PATH = Path("data/benchmarks/humaneval/HumanEval.jsonl.gz")


def generate_humaneval_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> List[TaskSpec]:
    records = load_humaneval_records(cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        task_id = str(record["task_id"]).replace("/", "-")
        prompt = str(record["prompt"])
        entry_point = str(record["entry_point"])
        tasks.append(
            TaskSpec(
                task_id=f"humaneval-{task_id}",
                family="humaneval",
                description=f"Solve the HumanEval Python programming task {record['task_id']}.",
                input_payload={
                    "prompt": prompt,
                    "entry_point": entry_point,
                    "source_task_id": record["task_id"],
                    "benchmark_source": "openai/human-eval",
                },
                hidden_oracle_payload={
                    "oracle_type": "humaneval",
                    "prompt": prompt,
                    "test": record["test"],
                    "entry_point": entry_point,
                    "timeout_seconds": 4,
                    "required_artifacts": ["solution.py"],
                    "require_evidence": False,
                },
                acceptance_criteria=[
                    "Candidate Python code defines or completes the requested entry point.",
                    "Official HumanEval tests pass in a subprocess.",
                ],
                metadata={
                    "benchmark": "humaneval",
                    "seed": seed,
                    "source_task_id": record["task_id"],
                    "source_index": records.index(record),
                    "selection_index": index,
                },
            )
        )
    return tasks


def load_humaneval_records(cache_path: Path = DEFAULT_CACHE_PATH) -> List[Dict[str, Any]]:
    if not cache_path.exists():
        _download_humaneval(cache_path)
    records: List[Dict[str, Any]] = []
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def _download_humaneval(cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(HUMANEVAL_URL, timeout=60) as response:
        cache_path.write_bytes(response.read())


def _select_records(records: List[Dict[str, Any]], n_tasks: int, seed: int) -> List[Dict[str, Any]]:
    if n_tasks <= 0 or n_tasks >= len(records):
        return list(records)
    start = (max(seed, 1) - 1) % len(records)
    rotated = records[start:] + records[:start]
    return rotated[:n_tasks]
