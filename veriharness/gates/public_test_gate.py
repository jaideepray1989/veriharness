from __future__ import annotations

import ast

from veriharness.benchmarks.oracles import (
    _assemble_humaneval_solution,
    _candidate_code,
    _run_humaneval_tests,
)
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class PublicTestGate:
    """Execute only the test explicitly exposed in the task input."""

    name = "public_test"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        if task.family != "humaneval_public":
            return GateResult(gate_name=self.name, passed=True, score=1.0)

        code = _candidate_code(output.answer)
        prompt = str(task.input_payload.get("prompt", ""))
        entry_point = str(task.input_payload.get("entry_point", ""))
        public_test = str(task.input_payload.get("public_test", ""))
        if not code.strip() or not public_test.strip():
            return GateResult(gate_name=self.name, passed=True, score=1.0)

        solution = _assemble_humaneval_solution(prompt, code, entry_point)
        result = _run_humaneval_tests(solution, public_test, entry_point, timeout=4)
        if result["passed"]:
            return GateResult(gate_name=self.name, passed=True, score=1.0)

        assertion = _assertion_text(public_test)
        failure = GateFailure(
            code=result["code"],
            message=result["message"],
            details={
                "location": f"public_test.{entry_point}",
                "expected": assertion or "the visible public test to pass",
                "observed": (result.get("stderr") or result["message"])[-800:],
            },
        )
        return GateResult(gate_name=self.name, passed=False, score=0.0, failures=[failure])


def _assertion_text(test: str) -> str:
    tree = ast.parse(test)
    assertion = next((node for node in ast.walk(tree) if isinstance(node, ast.Assert)), None)
    return ast.unparse(assertion) if assertion is not None else ""
