from __future__ import annotations

from veriharness.benchmarks.oracles import textworld_oracle
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateResult, LeafOutput, TaskSpec


class TextWorldGate:
    """Execute a candidate action plan against a fresh deterministic game state."""

    name = "textworld"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        if task.family != "textworld":
            return GateResult(gate_name=self.name, passed=True, score=1.0)
        result = textworld_oracle(task, output)
        return GateResult(
            gate_name=self.name,
            passed=result.passed,
            score=result.score,
            failures=result.failures,
            metadata=result.metadata,
        )
