from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from veriharness.core.types import TaskSpec

BOOLQ_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DEFAULT_BOOLQ_CACHE = Path("data/benchmarks/boolq/validation.json")
DEFAULT_SQUAD_CACHE = Path("data/benchmarks/squad/validation.json")


def generate_boolq_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_BOOLQ_CACHE,
) -> List[TaskSpec]:
    records = load_boolq_records(max(n_tasks + seed - 1, n_tasks), cache_path=cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_index = int(record["row_idx"])
        row = record["row"]
        answer = bool(row["answer"])
        tasks.append(
            TaskSpec(
                task_id=f"boolq-validation-{source_index:05d}",
                family="boolq",
                description="Answer the BoolQ yes/no question from the provided passage.",
                input_payload={
                    "question": row["question"],
                    "passage": row["passage"],
                    "title": row.get("title", ""),
                    "source_index": source_index,
                },
                hidden_oracle_payload={
                    "oracle_type": "boolq",
                    "answer": answer,
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=[
                    "Answer is a boolean.",
                    "Answer agrees with the BoolQ validation label.",
                ],
                metadata={
                    "benchmark": "boolq",
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": "google/boolq validation via Hugging Face dataset server",
                },
            )
        )
    return tasks


def generate_squad_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_SQUAD_CACHE,
) -> List[TaskSpec]:
    records = load_squad_records(cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_index = int(record["source_index"])
        answers = [answer["text"] for answer in record["answers"] if answer.get("text")]
        tasks.append(
            TaskSpec(
                task_id=f"squad-dev-{source_index:05d}",
                family="squad",
                description="Answer the SQuAD extractive QA question from the provided passage.",
                input_payload={
                    "question": record["question"],
                    "passage": record["context"],
                    "title": record["title"],
                    "source_id": record["id"],
                    "source_index": source_index,
                },
                hidden_oracle_payload={
                    "oracle_type": "squad",
                    "answers": answers,
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                    "min_f1": 0.8,
                },
                acceptance_criteria=[
                    "Answer is a short span or phrase from the passage.",
                    "Normalized answer has high token overlap with an accepted SQuAD answer.",
                ],
                metadata={
                    "benchmark": "squad",
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": "SQuAD v1.1 dev",
                },
            )
        )
    return tasks


def load_boolq_records(count: int, cache_path: Path = DEFAULT_BOOLQ_CACHE) -> List[Dict[str, Any]]:
    if not cache_path.exists() or _cached_rows(cache_path) < count:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        params = urllib.parse.urlencode(
            {
                "dataset": "google/boolq",
                "config": "default",
                "split": "validation",
                "offset": 0,
                "length": max(count, 100),
            }
        )
        with urllib.request.urlopen(f"{BOOLQ_ROWS_URL}?{params}", timeout=60) as response:
            payload = json.loads(response.read())
        cache_path.write_text(json.dumps(payload["rows"], indent=2) + "\n", encoding="utf-8")
    return json.loads(cache_path.read_text(encoding="utf-8"))


def load_squad_records(cache_path: Path = DEFAULT_SQUAD_CACHE) -> List[Dict[str, Any]]:
    if not cache_path.exists():
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        params = urllib.parse.urlencode(
            {
                "dataset": "rajpurkar/squad",
                "config": "plain_text",
                "split": "validation",
                "offset": 0,
                "length": 100,
            }
        )
        with urllib.request.urlopen(f"{BOOLQ_ROWS_URL}?{params}", timeout=60) as response:
            payload = json.loads(response.read())
        rows = [
            {
                "source_index": int(item["row_idx"]),
                "id": item["row"].get("id", ""),
                "title": item["row"].get("title", ""),
                "context": item["row"].get("context", ""),
                "question": item["row"].get("question", ""),
                "answers": _squad_answers(item["row"].get("answers", {})),
            }
            for item in payload["rows"]
        ]
        cache_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return json.loads(cache_path.read_text(encoding="utf-8"))


def _load_squad_records_from_dev_json(cache_path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(cache_path.read_text(encoding="utf-8"))
    records: List[Dict[str, Any]] = []
    source_index = 0
    for article in payload["data"]:
        title = article.get("title", "")
        for paragraph in article.get("paragraphs", []):
            context = paragraph.get("context", "")
            for qa in paragraph.get("qas", []):
                records.append(
                    {
                        "source_index": source_index,
                        "id": qa.get("id", ""),
                        "title": title,
                        "context": context,
                        "question": qa.get("question", ""),
                        "answers": qa.get("answers", []),
                    }
                )
                source_index += 1
    return records


def _squad_answers(value: Dict[str, Any]) -> List[Dict[str, Any]]:
    texts = value.get("text", []) if isinstance(value, dict) else []
    starts = value.get("answer_start", []) if isinstance(value, dict) else []
    answers: List[Dict[str, Any]] = []
    for index, text in enumerate(texts):
        start = starts[index] if index < len(starts) else -1
        answers.append({"text": text, "answer_start": start})
    return answers


def _cached_rows(cache_path: Path) -> int:
    try:
        return len(json.loads(cache_path.read_text(encoding="utf-8")))
    except Exception:
        return 0


def _select_records(records: List[Dict[str, Any]], n_tasks: int, seed: int) -> List[Dict[str, Any]]:
    if n_tasks <= 0 or n_tasks >= len(records):
        return list(records)
    start = (max(seed, 1) - 1) % len(records)
    rotated = records[start:] + records[:start]
    return rotated[:n_tasks]
