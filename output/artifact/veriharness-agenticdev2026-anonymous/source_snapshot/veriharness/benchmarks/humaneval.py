from __future__ import annotations

import ast
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


def generate_humaneval_public_tasks(
    n_tasks: int = 50,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_PATH,
) -> List[TaskSpec]:
    """HumanEval tasks with one public assertion and the full suite held out."""
    records = load_humaneval_records(cache_path)
    eligible = [(record, _public_test_prefix(str(record["test"]))) for record in records]
    eligible = [(record, public) for record, public in eligible if public is not None]
    selected = _select_records([record for record, _public in eligible], n_tasks=n_tasks, seed=seed)
    public_by_id = {str(record["task_id"]): public for record, public in eligible}
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_id = str(record["task_id"])
        task_id = source_id.replace("/", "-")
        prompt = str(record["prompt"])
        entry_point = str(record["entry_point"])
        public_test = str(public_by_id[source_id])
        tasks.append(
            TaskSpec(
                task_id=f"humaneval-public-{task_id}",
                family="humaneval_public",
                description=f"Solve {source_id} using the visible public test; hidden tests are post-hoc only.",
                input_payload={
                    "prompt": prompt,
                    "entry_point": entry_point,
                    "public_test": public_test,
                    "source_task_id": source_id,
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
                    "Candidate code passes the visible public assertion.",
                    "The complete official HumanEval test suite is used only for post-hoc scoring.",
                ],
                metadata={
                    "benchmark": "humaneval_public",
                    "seed": seed,
                    "source_task_id": source_id,
                    "source_index": records.index(record),
                    "selection_index": index,
                    "public_test_rule": "prefix_through_first_top_level_assert_v1",
                },
            )
        )
    return tasks


def _public_test_prefix(test: str) -> str | None:
    tree = ast.parse(test)
    check = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "check"),
        None,
    )
    if check is None:
        return None
    assertion_index = next(
        (index for index, node in enumerate(check.body) if isinstance(node, ast.Assert)),
        None,
    )
    if assertion_index is None:
        return None
    check.body = check.body[: assertion_index + 1]
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


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
