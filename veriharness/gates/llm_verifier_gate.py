from __future__ import annotations

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class LLMVerifierGate:
    name = "llm_verifier"
    hard = False

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        risks = output.self_assessment.get("risks", [])
        failures = []
        if isinstance(risks, list) and any("unsupported" in str(risk).lower() for risk in risks):
            failures.append(GateFailure(code="verifier_risk", message="Verifier found unsupported-risk marker."))
        return GateResult(gate_name=self.name, passed=not failures, score=0.5 if failures else 1.0, failures=failures)
