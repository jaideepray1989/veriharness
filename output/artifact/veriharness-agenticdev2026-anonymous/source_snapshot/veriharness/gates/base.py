from __future__ import annotations

from typing import Protocol

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateResult, LeafOutput, TaskSpec


class Gate(Protocol):
    name: str
    hard: bool

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        ...
