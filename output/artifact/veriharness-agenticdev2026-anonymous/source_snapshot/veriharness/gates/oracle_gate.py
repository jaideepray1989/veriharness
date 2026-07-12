from __future__ import annotations

from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateResult, LeafOutput, TaskSpec


class OracleGate:
    name = "oracle"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        return evaluate_oracle(task, output)
