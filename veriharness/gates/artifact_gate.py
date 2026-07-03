from __future__ import annotations

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class ArtifactGate:
    name = "artifact"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        required = task.hidden_oracle_payload.get("required_artifacts", [])
        failures = []
        for artifact in required:
            if artifact not in output.artifacts:
                failures.append(
                    GateFailure(code="artifact_missing", message=f"Required artifact not listed: {artifact}")
                )
                continue
            if not store.path(f"{leaf_dir}/{artifact}").exists():
                failures.append(
                    GateFailure(code="artifact_missing", message=f"Required artifact not written: {artifact}")
                )
        return GateResult(gate_name=self.name, passed=not failures, score=0.0 if failures else 1.0, failures=failures)
