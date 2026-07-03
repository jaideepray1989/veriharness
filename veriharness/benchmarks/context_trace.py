from __future__ import annotations

import random
from typing import Iterable, List

from veriharness.core.types import TaskSpec

CONSTRAINT_POSITIONS = ["early", "middle", "late"]
NOISE_TYPES = ["irrelevant", "wrong_prior_attempt", "conflicting_doc"]
TASK_TYPES = ["config_generation", "report_generation", "simple_code"]


def _insert_at(trace: List[str], position: str, item: str) -> None:
    if position == "early":
        index = 0
    elif position == "middle":
        index = max(0, len(trace) // 2)
    else:
        index = max(0, len(trace) - 1)
    trace[index] = item


def generate_context_trace_tasks(
    n_tasks: int = 10,
    trace_lengths: Iterable[int] = (4, 8),
    seed: int = 1,
) -> List[TaskSpec]:
    rng = random.Random(seed)
    lengths = list(trace_lengths)
    tasks: List[TaskSpec] = []
    for i in range(n_tasks):
        trace_length = lengths[i % len(lengths)]
        position = CONSTRAINT_POSITIONS[i % len(CONSTRAINT_POSITIONS)]
        noise_type = NOISE_TYPES[(i + seed) % len(NOISE_TYPES)]
        task_type = TASK_TYPES[i % len(TASK_TYPES)]
        trace = [f"Turn {j + 1}: irrelevant progress note {rng.randint(1, 999)}." for j in range(trace_length)]
        invariant = "User requires export_format=jsonl and fields id,value."
        _insert_at(trace, position, invariant)
        distractors = []
        if noise_type == "wrong_prior_attempt":
            distractors.append("Prior failed attempt used export_format=csv.")
        elif noise_type == "conflicting_doc":
            distractors.append("Legacy documentation says CSV is preferred.")
        else:
            distractors.append("Unrelated note about chart colors.")
        trace.extend(distractors)
        task_id = f"context-trace-s{seed}-{i:03d}"
        tasks.append(
            TaskSpec(
                task_id=task_id,
                family="context_trace",
                description="Produce the export config while preserving the active trace invariant.",
                input_payload={
                    "raw_trace": trace,
                    "trace_distractors": distractors,
                    "required_fields": ["id", "value"],
                    "constraints": ["Output config must use JSONL."],
                    "distractors": distractors,
                },
                hidden_oracle_payload={
                    "oracle_type": "context_trace",
                    "expected_export_format": "jsonl",
                    "forbidden_export_format": "csv",
                    "required_artifacts": ["answer.json"],
                    "require_evidence": True,
                    "deterministic_checks": [
                        {"type": "json_field_equals", "field": "export_format", "value": "jsonl"},
                        {"type": "forbidden_substring", "value": '"export_format": "csv"'},
                    ],
                },
                acceptance_criteria=[
                    "export_format == jsonl",
                    "export_format != csv",
                    "fields id and value are present",
                ],
                metadata={
                    "benchmark": "context_trace",
                    "seed": seed,
                    "trace_length": trace_length,
                    "constraint_position": position,
                    "noise_type": noise_type,
                    "task_type": task_type,
                },
            )
        )
    return tasks
