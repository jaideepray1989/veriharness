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

HELDOUT_WORKFLOWS = [
    ("index-rebuild", "Rebuild the index while preserving stable document identifiers.", "stable_ids_retained"),
    ("api-versioning", "Add API versioning without changing the default response shape.", "default_shape_retained"),
    ("cache-invalidation", "Invalidate stale cache entries while preserving fresh entries.", "fresh_entries_retained"),
    ("audit-export", "Add an audit field while retaining the canonical export representation.", "canonical_export_retained"),
    ("feature-flag", "Introduce a feature flag without changing the disabled-path behavior.", "disabled_path_retained"),
    ("deduplication", "Deduplicate records while preserving the first-seen canonical record.", "canonical_record_retained"),
    ("path-migration", "Migrate storage paths while preserving existing relative references.", "relative_refs_retained"),
    ("retry-policy", "Add a retry policy without changing the successful first-attempt result.", "first_attempt_retained"),
    ("timezone-normalization", "Normalize timestamps while preserving their represented instant.", "instant_retained"),
    ("permission-check", "Add a permission check without changing authorized-user behavior.", "authorized_behavior_retained"),
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


def generate_mini_workflow_heldout_tasks(n_tasks: int = 200, seed: int = 1) -> List[TaskSpec]:
    """Generate deterministic held-out workflow instances without reusing base markers."""
    tasks: List[TaskSpec] = []
    for i in range(n_tasks):
        name, instruction, base_marker = HELDOUT_WORKFLOWS[i % len(HELDOUT_WORKFLOWS)]
        marker = f"{base_marker}_s{seed}_{i:03d}"
        task_id = f"mini-workflow-heldout-s{seed}-{i:03d}"
        tasks.append(
            TaskSpec(
                task_id=task_id,
                family="mini_workflow",
                description=f"{instruction} Record completion marker {marker} in the workflow result.",
                input_payload={
                    "workflow": name,
                    "visible_instruction": f"{instruction} Record completion marker {marker}.",
                    "raw_trace": [
                        "Early invariant: preserve the existing compatible behavior.",
                        "Legacy document distractor: an obsolete csv migration is mentioned.",
                        "Final task: implement the requested change while retaining the invariant.",
                    ],
                    "invariants": [f"Expected result marker: {marker}"],
                    "wrong_docs": ["Reject legacy csv migration guidance."],
                },
                hidden_oracle_payload={
                    "oracle_type": "mini_workflow",
                    "expected_substring": marker,
                    "forbidden_substring": "csv",
                    "required_artifacts": ["workflow_patch.txt"],
                    "require_evidence": True,
                    "deterministic_checks": [
                        {"type": "expected_substring", "value": marker},
                        {"type": "forbidden_substring", "value": '"result": "csv"'},
                    ],
                },
                acceptance_criteria=[
                    "Expected held-out marker appears in the result.",
                    "Legacy csv guidance is absent from the final result.",
                    "The workflow patch artifact and evidence are present.",
                ],
                metadata={
                    "benchmark": "mini_workflow_heldout",
                    "seed": seed,
                    "workflow": name,
                    "template_set": "heldout-v1",
                    "selection_index": i,
                },
            )
        )
    return tasks
