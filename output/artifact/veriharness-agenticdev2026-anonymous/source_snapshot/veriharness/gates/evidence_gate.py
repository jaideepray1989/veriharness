from __future__ import annotations

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class EvidenceGate:
    name = "evidence"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        if not task.hidden_oracle_payload.get("require_evidence", True):
            return GateResult(gate_name=self.name, passed=True, score=1.0)
        failures = [
            GateFailure(code="claim_without_evidence", message=f"Claim lacks evidence: {claim.claim}")
            for claim in output.claims
            if not claim.evidence_refs
        ]
        if not output.claims:
            failures.append(GateFailure(code="claim_without_evidence", message="Output has no explicit claims."))
        return GateResult(gate_name=self.name, passed=not failures, score=0.0 if failures else 1.0, failures=failures)
