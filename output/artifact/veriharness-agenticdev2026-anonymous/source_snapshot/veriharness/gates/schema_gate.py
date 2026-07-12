from __future__ import annotations

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class SchemaGate:
    name = "schema"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        failures = []
        if output.task_id != task.task_id:
            failures.append(GateFailure(code="task_id_mismatch", message="Output task_id does not match task."))
        if output.self_assessment.get("parse_error"):
            failures.append(
                GateFailure(
                    code="schema_invalid",
                    message="Leaf output could not be parsed as valid structured output.",
                    details={"parse_error": output.self_assessment.get("parse_error")},
                )
            )
        if output.self_assessment.get("client_error"):
            failures.append(
                GateFailure(
                    code="client_error",
                    message="Leaf client failed before producing structured output.",
                    details={"client_error": output.self_assessment.get("client_error")},
                )
            )
        if not output.answer:
            failures.append(GateFailure(code="empty_answer", message="Leaf answer is empty."))
        return GateResult(gate_name=self.name, passed=not failures, score=0.0 if failures else 1.0, failures=failures)
