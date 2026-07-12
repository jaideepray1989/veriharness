from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List

from veriharness.core.types import TaskSpec

HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DEFAULT_CACHE_ROOT = Path("data/benchmarks")

SWE_BENCHMARKS = {
    "swebench_lite": {
        "dataset": "princeton-nlp/SWE-bench_Lite",
        "split": "test",
        "cache": DEFAULT_CACHE_ROOT / "swebench_lite" / "test.json",
        "description": "Produce a patch for a SWE-bench Lite GitHub issue.",
    },
    "swebench_verified": {
        "dataset": "princeton-nlp/SWE-bench_Verified",
        "split": "test",
        "cache": DEFAULT_CACHE_ROOT / "swebench_verified" / "test.json",
        "description": "Produce a patch for a SWE-bench Verified GitHub issue.",
    },
}

MLAGENTBENCH_TASKS = [
    "cifar10",
    "imdb",
    "ogbn-arxiv",
    "house-price",
    "spaceship-titanic",
    "feedback",
    "fathomnet",
    "identify-contrails",
    "amp-parkinsons-disease-progression-prediction",
    "babylm",
    "CLRS",
    "vectorization",
    "llama-inference",
]


def generate_swebench_tasks(benchmark: str, n_tasks: int = 20, seed: int = 1) -> List[TaskSpec]:
    spec = SWE_BENCHMARKS[benchmark]
    records = load_hf_rows(spec["dataset"], "default", spec["split"], spec["cache"])
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for selection_index, record in enumerate(selected):
        row = record["row"]
        instance_id = str(row["instance_id"])
        fail_to_pass = _json_list(row.get("FAIL_TO_PASS", "[]"))
        pass_to_pass = _json_list(row.get("PASS_TO_PASS", "[]"))
        tasks.append(
            TaskSpec(
                task_id=f"{benchmark}-{_safe_id(instance_id)}",
                family="swebench_patch",
                description=spec["description"],
                input_payload={
                    "repo": row.get("repo", ""),
                    "instance_id": instance_id,
                    "base_commit": row.get("base_commit", ""),
                    "problem_statement": row.get("problem_statement", ""),
                    "hints_text": row.get("hints_text", ""),
                    "fail_to_pass": fail_to_pass,
                    "pass_to_pass": pass_to_pass,
                    "benchmark_name": benchmark,
                },
                hidden_oracle_payload={
                    "oracle_type": "swebench_patch",
                    "reference_patch": row.get("patch", ""),
                    "test_patch": row.get("test_patch", ""),
                    "required_artifacts": ["patch.diff"],
                    "require_evidence": False,
                    "external_eval": {
                        "required": True,
                        "runner": "swebench.harness.run_evaluation",
                        "dataset": spec["dataset"],
                        "instance_id": instance_id,
                        "note": "Reference-patch oracle is for adapter smoke tests; paper scoring must use SWE-bench containers.",
                    },
                },
                acceptance_criteria=[
                    "Return a unified diff patch as patch.diff.",
                    "Patch should address FAIL_TO_PASS tests without regressing PASS_TO_PASS tests.",
                    "Paper-quality scoring must run the official SWE-bench evaluation harness.",
                ],
                metadata={
                    "benchmark": benchmark,
                    "seed": seed,
                    "source": f"{spec['dataset']} {spec['split']} via Hugging Face dataset server",
                    "source_index": int(record["row_idx"]),
                    "selection_index": selection_index,
                    "repo": row.get("repo", ""),
                    "external_eval_required": True,
                },
            )
        )
    return tasks


def generate_ds1000_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "ds1000" / "test.json",
) -> List[TaskSpec]:
    records = load_hf_rows("xlangai/DS-1000", "default", "test", cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for selection_index, record in enumerate(selected):
        row = record["row"]
        metadata = row.get("metadata", {}) or {}
        problem_id = metadata.get("problem_id", record["row_idx"])
        library = str(metadata.get("library", "unknown"))
        tasks.append(
            TaskSpec(
                task_id=f"ds1000-{int(problem_id):04d}",
                family="ds1000",
                description=f"Solve DS-1000 data-science coding problem {problem_id} ({library}).",
                input_payload={
                    "prompt": row.get("prompt", ""),
                    "code_context": row.get("code_context", ""),
                    "library": library,
                    "problem_id": problem_id,
                    "benchmark_name": "ds1000",
                },
                hidden_oracle_payload={
                    "oracle_type": "ds1000",
                    "code_context": row.get("code_context", ""),
                    "reference_code": row.get("reference_code", ""),
                    "timeout_seconds": 8,
                    "required_artifacts": ["solution.py"],
                    "require_evidence": False,
                },
                acceptance_criteria=[
                    "Candidate code sets variable result in the DS-1000 execution context.",
                    "The benchmark-provided test_execution function passes.",
                ],
                metadata={
                    "benchmark": "ds1000",
                    "seed": seed,
                    "source": "xlangai/DS-1000 test via Hugging Face dataset server",
                    "source_index": int(record["row_idx"]),
                    "selection_index": selection_index,
                    "library": library,
                    "problem_id": problem_id,
                },
            )
        )
    return tasks


def generate_mlagentbench_tasks(n_tasks: int = 13, seed: int = 1) -> List[TaskSpec]:
    selected_names = _select_items(MLAGENTBENCH_TASKS, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for selection_index, task_name in enumerate(selected_names):
        research_problem = fetch_mlagentbench_research_problem(task_name)
        tasks.append(
            TaskSpec(
                task_id=f"mlagentbench-{_safe_id(task_name)}",
                family="mlagentbench",
                description=f"Prepare an MLAgentBench experiment plan for {task_name}.",
                input_payload={
                    "task_name": task_name,
                    "research_problem": research_problem,
                    "upstream_repo": "snap-stanford/MLAgentBench",
                    "benchmark_path": f"MLAgentBench/benchmarks/{task_name}",
                    "benchmark_name": "mlagentbench",
                },
                hidden_oracle_payload={
                    "oracle_type": "mlagentbench_manifest",
                    "task_name": task_name,
                    "required_artifacts": ["research_plan.json"],
                    "require_evidence": False,
                    "external_eval": {
                        "required": True,
                        "runner": "python -m MLAgentBench.runner",
                        "eval": "python -m MLAgentBench.eval",
                        "note": "VeriHarness manifest oracle validates runnable experiment metadata; paper scoring must use upstream MLAgentBench.",
                    },
                },
                acceptance_criteria=[
                    "Return a JSON research plan naming train/eval commands and expected artifacts.",
                    "Include an MLAgentBench task name and an output artifact such as submission.csv or metrics.json.",
                    "Paper-quality scoring must run the upstream MLAgentBench environment.",
                ],
                metadata={
                    "benchmark": "mlagentbench",
                    "seed": seed,
                    "source": "snap-stanford/MLAgentBench GitHub repository",
                    "selection_index": selection_index,
                    "task_name": task_name,
                    "external_eval_required": True,
                },
            )
        )
    return tasks


def load_hf_rows(
    dataset: str,
    config: str,
    split: str,
    cache_path: Path,
    *,
    length: int = 100,
) -> List[Dict[str, Any]]:
    if not cache_path.exists() or _cached_rows(cache_path) < length:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        params = urllib.parse.urlencode(
            {
                "dataset": dataset,
                "config": config,
                "split": split,
                "offset": 0,
                "length": length,
            }
        )
        with urllib.request.urlopen(f"{HF_ROWS_URL}?{params}", timeout=60) as response:
            payload = json.loads(response.read())
        cache_path.write_text(json.dumps(payload["rows"], indent=2) + "\n", encoding="utf-8")
    return json.loads(cache_path.read_text(encoding="utf-8"))


def fetch_mlagentbench_research_problem(task_name: str) -> str:
    url = (
        "https://raw.githubusercontent.com/snap-stanford/MLAgentBench/main/"
        f"MLAgentBench/benchmarks/{task_name}/scripts/research_problem.txt"
    )
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            return response.read().decode("utf-8").strip()
    except Exception:
        return "Improve the baseline ML system for this MLAgentBench task and produce an evaluable submission."


def _cached_rows(path: Path) -> int:
    try:
        return len(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return 0


def _json_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        decoded = json.loads(str(value))
    except Exception:
        return []
    if isinstance(decoded, list):
        return [str(item) for item in decoded]
    return []


def _select_records(records: List[Dict[str, Any]], n_tasks: int, seed: int) -> List[Dict[str, Any]]:
    if n_tasks <= 0 or n_tasks >= len(records):
        return list(records)
    rng = random.Random(seed)
    indices = list(range(len(records)))
    rng.shuffle(indices)
    return [records[index] for index in indices[:n_tasks]]


def _select_items(items: Iterable[str], n_tasks: int, seed: int) -> List[str]:
    materialized = list(items)
    if n_tasks <= 0 or n_tasks >= len(materialized):
        return materialized
    rng = random.Random(seed)
    indices = list(range(len(materialized)))
    rng.shuffle(indices)
    return [materialized[index] for index in indices[:n_tasks]]


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in value)[:120]
