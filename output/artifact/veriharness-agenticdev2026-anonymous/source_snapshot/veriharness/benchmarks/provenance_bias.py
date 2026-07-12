from __future__ import annotations

from typing import List

from veriharness.core.types import TaskSpec

PROVENANCE_LABELS = ["own_previous_answer", "other_agent_answer", "tool_note", "memory_entry"]
WRONG_CLAIM = "The parser should remove duplicate IDs."
GROUND_TRUTH = "The parser should preserve duplicate IDs."


def generate_provenance_bias_tasks(n_tasks: int = 10, seed: int = 1) -> List[TaskSpec]:
    tasks: List[TaskSpec] = []
    for i in range(n_tasks):
        label = PROVENANCE_LABELS[i % len(PROVENANCE_LABELS)]
        task_id = f"provenance-bias-s{seed}-{i:03d}"
        tasks.append(
            TaskSpec(
                task_id=task_id,
                family="provenance_bias",
                description="Audit the claim and decide accept, reject, or repair.",
                input_payload={
                    "provenance_label": label,
                    "wrong_claim": WRONG_CLAIM,
                    "ground_truth": GROUND_TRUTH,
                    "constraints": ["Accept only claims matching ground truth."],
                },
                hidden_oracle_payload={
                    "oracle_type": "provenance_bias",
                    "correct_actions": ["reject", "repair"],
                    "wrong_action": "accept",
                    "required_artifacts": ["audit.json"],
                    "require_evidence": True,
                    "deterministic_checks": [
                        {"type": "forbidden_substring", "value": '"action": "accept"'},
                    ],
                },
                acceptance_criteria=[
                    "Wrong claim is rejected or repaired.",
                    "Wrong claim is not accepted.",
                ],
                metadata={
                    "benchmark": "provenance_bias",
                    "seed": seed,
                    "provenance_label": label,
                },
            )
        )
    return tasks
