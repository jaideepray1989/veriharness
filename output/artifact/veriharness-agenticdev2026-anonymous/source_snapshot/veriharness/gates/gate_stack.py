from __future__ import annotations

from typing import Iterable, List

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateResult, LeafOutput, TaskSpec
from veriharness.gates.artifact_gate import ArtifactGate
from veriharness.gates.code_sanity_gate import CodeSanityGate
from veriharness.gates.deterministic_gate import DeterministicGate
from veriharness.gates.evidence_gate import EvidenceGate
from veriharness.gates.llm_verifier_gate import LLMVerifierGate
from veriharness.gates.oracle_gate import OracleGate
from veriharness.gates.public_test_gate import PublicTestGate
from veriharness.gates.schema_gate import SchemaGate
from veriharness.gates.textworld_gate import TextWorldGate


class GateStack:
    def __init__(self, gates: Iterable[object] | None = None, *, include_oracle: bool = True) -> None:
        if gates is not None:
            self.gates = list(gates)
            return
        self.gates = [
            SchemaGate(),
            ArtifactGate(),
            EvidenceGate(),
            CodeSanityGate(),
            PublicTestGate(),
            TextWorldGate(),
            DeterministicGate(),
        ]
        if include_oracle:
            self.gates.append(OracleGate())
        self.gates.append(LLMVerifierGate())

    def evaluate(
        self,
        task: TaskSpec,
        output: LeafOutput,
        store: ArtifactStore,
        leaf_dir: str,
    ) -> tuple[bool, List[GateResult]]:
        results: List[GateResult] = []
        hard_pass = True
        for gate in self.gates:
            result = gate.evaluate(task, output, store, leaf_dir)
            results.append(result)
            if getattr(gate, "hard", True) and not result.passed:
                hard_pass = False
        return hard_pass, results
