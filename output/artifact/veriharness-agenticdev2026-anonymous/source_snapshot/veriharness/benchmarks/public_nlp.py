from __future__ import annotations

import json
import random
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Tuple

from veriharness.core.types import TaskSpec

HF_ROWS_URL = "https://datasets-server.huggingface.co/rows"
DEFAULT_CACHE_ROOT = Path("data/benchmarks")


def generate_sciq_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "sciq" / "validation.json",
) -> List[TaskSpec]:
    records = load_hf_rows("allenai/sciq", "default", "validation", cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_index = int(record["row_idx"])
        row = record["row"]
        choices = [
            str(row["correct_answer"]),
            str(row["distractor1"]),
            str(row["distractor2"]),
            str(row["distractor3"]),
        ]
        labeled_choices, answer_label = _labeled_choices(choices, str(row["correct_answer"]), seed + source_index)
        tasks.append(
            TaskSpec(
                task_id=f"sciq-validation-{source_index:05d}",
                family="multiple_choice",
                description="Answer the SciQ science multiple-choice question.",
                input_payload={
                    "question": row["question"],
                    "support": row.get("support", ""),
                    "choices": labeled_choices,
                    "source_index": source_index,
                    "benchmark_name": "sciq",
                },
                hidden_oracle_payload={
                    "oracle_type": "multiple_choice",
                    "answer_label": answer_label,
                    "answer_text": str(row["correct_answer"]),
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=["Select the correct multiple-choice label."],
                metadata={
                    "benchmark": "sciq",
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": "allenai/sciq validation via Hugging Face dataset server",
                },
            )
        )
    return tasks


def generate_arc_easy_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "arc_easy" / "validation.json",
) -> List[TaskSpec]:
    records = load_hf_rows("allenai/ai2_arc", "ARC-Easy", "validation", cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_index = int(record["row_idx"])
        row = record["row"]
        choices = [
            {"label": str(label), "text": str(text)}
            for label, text in zip(row["choices"]["label"], row["choices"]["text"])
        ]
        answer_label = str(row["answerKey"])
        answer_text = next((choice["text"] for choice in choices if choice["label"] == answer_label), "")
        tasks.append(
            TaskSpec(
                task_id=f"arc-easy-validation-{source_index:05d}",
                family="multiple_choice",
                description="Answer the ARC-Easy grade-school science multiple-choice question.",
                input_payload={
                    "question": row["question"],
                    "choices": choices,
                    "source_id": row.get("id", ""),
                    "source_index": source_index,
                    "benchmark_name": "arc_easy",
                },
                hidden_oracle_payload={
                    "oracle_type": "multiple_choice",
                    "answer_label": answer_label,
                    "answer_text": answer_text,
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=["Select the correct multiple-choice label."],
                metadata={
                    "benchmark": "arc_easy",
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": "allenai/ai2_arc ARC-Easy validation via Hugging Face dataset server",
                },
            )
        )
    return tasks


def generate_glue_sst2_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "glue_sst2" / "validation.json",
) -> List[TaskSpec]:
    return _generate_text_classification_tasks(
        benchmark="glue_sst2",
        family_description="Classify the SST-2 sentence sentiment.",
        dataset="nyu-mll/glue",
        config="sst2",
        split="validation",
        cache_path=cache_path,
        n_tasks=n_tasks,
        seed=seed,
        labels={0: "negative", 1: "positive"},
        text_fields=["sentence"],
        source="nyu-mll/glue sst2 validation via Hugging Face dataset server",
    )


def generate_glue_rte_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "glue_rte" / "validation.json",
) -> List[TaskSpec]:
    return _generate_text_classification_tasks(
        benchmark="glue_rte",
        family_description="Classify the RTE sentence pair as entailment or not_entailment.",
        dataset="nyu-mll/glue",
        config="rte",
        split="validation",
        cache_path=cache_path,
        n_tasks=n_tasks,
        seed=seed,
        labels={0: "entailment", 1: "not_entailment"},
        text_fields=["sentence1", "sentence2"],
        source="nyu-mll/glue rte validation via Hugging Face dataset server",
    )


def generate_glue_mrpc_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "glue_mrpc" / "validation.json",
) -> List[TaskSpec]:
    return _generate_text_classification_tasks(
        benchmark="glue_mrpc",
        family_description="Classify the MRPC sentence pair as equivalent or not_equivalent.",
        dataset="nyu-mll/glue",
        config="mrpc",
        split="validation",
        cache_path=cache_path,
        n_tasks=n_tasks,
        seed=seed,
        labels={0: "not_equivalent", 1: "equivalent"},
        text_fields=["sentence1", "sentence2"],
        source="nyu-mll/glue mrpc validation via Hugging Face dataset server",
    )


def generate_trec_qc_tasks(
    n_tasks: int = 20,
    seed: int = 1,
    cache_path: Path = DEFAULT_CACHE_ROOT / "trec_qc" / "test.json",
) -> List[TaskSpec]:
    records = load_hf_rows("SetFit/TREC-QC", "default", "test", cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    labels = ["ABBR", "DESC", "ENTY", "HUM", "LOC", "NUM"]
    label_aliases = {
        "ABBR": ["abbreviation", "abbreviated expression"],
        "DESC": ["description", "definition", "description or definition"],
        "ENTY": ["entity", "thing", "object"],
        "HUM": ["human", "person", "people"],
        "LOC": ["location", "place"],
        "NUM": ["number", "numeric", "numeric value", "quantity"],
    }
    tasks: List[TaskSpec] = []
    for index, record in enumerate(selected):
        source_index = int(record["row_idx"])
        row = record["row"]
        label = str(row["label_coarse_original"])
        tasks.append(
            TaskSpec(
                task_id=f"trec-qc-test-{source_index:05d}",
                family="text_classification",
                description="Classify the TREC question into its coarse answer type.",
                input_payload={
                    "text": row["text"],
                    "labels": labels,
                    "label_descriptions": {
                        "ABBR": "abbreviation",
                        "DESC": "description or definition",
                        "ENTY": "entity",
                        "HUM": "human",
                        "LOC": "location",
                        "NUM": "numeric value",
                    },
                    "source_index": source_index,
                    "benchmark_name": "trec_qc",
                },
                hidden_oracle_payload={
                    "oracle_type": "text_classification",
                    "label": label,
                    "accepted_labels": labels,
                    "accepted_aliases": label_aliases,
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=["Return the correct coarse TREC question class label."],
                metadata={
                    "benchmark": "trec_qc",
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": "SetFit/TREC-QC test via Hugging Face dataset server",
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


def _generate_text_classification_tasks(
    *,
    benchmark: str,
    family_description: str,
    dataset: str,
    config: str,
    split: str,
    cache_path: Path,
    n_tasks: int,
    seed: int,
    labels: Dict[int, str],
    text_fields: List[str],
    source: str,
) -> List[TaskSpec]:
    records = load_hf_rows(dataset, config, split, cache_path)
    selected = _select_records(records, n_tasks=n_tasks, seed=seed)
    tasks: List[TaskSpec] = []
    accepted_labels = list(labels.values())
    for index, record in enumerate(selected):
        source_index = int(record["row_idx"])
        row = record["row"]
        label = labels[int(row["label"])]
        input_payload = {
            "labels": accepted_labels,
            "source_index": source_index,
            "benchmark_name": benchmark,
        }
        for field in text_fields:
            input_payload[field] = row[field]
        tasks.append(
            TaskSpec(
                task_id=f"{benchmark}-{split}-{source_index:05d}",
                family="text_classification",
                description=family_description,
                input_payload=input_payload,
                hidden_oracle_payload={
                    "oracle_type": "text_classification",
                    "label": label,
                    "accepted_labels": accepted_labels,
                    "required_artifacts": ["answer.json"],
                    "require_evidence": False,
                },
                acceptance_criteria=["Return exactly one label from the provided label set."],
                metadata={
                    "benchmark": benchmark,
                    "seed": seed,
                    "source_index": source_index,
                    "selection_index": index,
                    "source": source,
                },
            )
        )
    return tasks


def _labeled_choices(choices: List[str], correct_answer: str, seed: int) -> Tuple[List[Dict[str, str]], str]:
    shuffled = list(choices)
    random.Random(seed).shuffle(shuffled)
    labels = ["A", "B", "C", "D"]
    labeled = [{"label": label, "text": text} for label, text in zip(labels, shuffled)]
    answer_label = next(item["label"] for item in labeled if item["text"] == correct_answer)
    return labeled, answer_label


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
