from __future__ import annotations

from typing import List

from veriharness.core.types import TaskSpec

WORKFLOWS = [
    ("parser-bug", "Preserve duplicate IDs while fixing parser bug.", "duplicate_ids_preserved"),
    ("config-migration", "Migrate config while preserving default jsonl output.", "jsonl"),
    ("report-synthesis", "Synthesize conflicting files while retaining source priority.", "source_priority"),
    ("cli-behavior", "Add a flag without changing existing CLI default.", "default_jsonl"),
    ("data-export", "Preserve data export format while adding metadata.", "export_jsonl"),
]


def generate_mini_workflow_tasks(n_tasks: int = 5, seed: int = 1) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for i in range(n_tasks):
        name, instruction, expected = WORKFLOWS[i % len(WORKFLOWS)]
        task_id = f"mini-workflow-s{seed}-{i:03d}"
        tasks.append(
            TaskSpec(
                task_id=task_id,
                family="mini_workflow",
                description=instruction,
                input_payload={
                    "workflow": name,
                    "visible_instruction": instruction,
                    "raw_trace": [
                        "Early invariant: default remains jsonl.",
                        "Legacy doc distractor: csv examples are shown.",
                        "Final task: implement requested change.",
                    ],
                    "invariants": [f"Expected result marker: {expected}"],
                    "wrong_docs": ["Reject legacy csv default."],
                },
                hidden_oracle_payload={
                    "oracle_type": "mini_workflow",
                    "expected_substring": expected,
                    "forbidden_substring": "csv",
                    "required_artifacts": ["workflow_patch.txt"],
                    "require_evidence": True,
                    "deterministic_checks": [
                        {"type": "expected_substring", "value": expected},
                        {"type": "forbidden_substring", "value": '"result": "csv"'},
                    ],
                },
                acceptance_criteria=[
                    "Expected marker appears in output.",
                    "Forbidden legacy csv default is absent.",
                    "Expected artifact is present.",
                ],
                metadata={"benchmark": "mini_workflow", "seed": seed, "workflow": name},
            )
        )
    return tasks
