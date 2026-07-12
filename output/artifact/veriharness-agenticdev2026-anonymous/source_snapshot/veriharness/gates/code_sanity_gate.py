from __future__ import annotations

import ast
import re

from veriharness.benchmarks.oracles import _candidate_code
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


class CodeSanityGate:
    """Non-oracle validation for executable-code tasks."""

    name = "code_sanity"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        if task.family not in {"humaneval", "humaneval_public", "ds1000"}:
            return GateResult(gate_name=self.name, passed=True, score=1.0)

        code = _candidate_code(output.answer)
        failures = []
        if not code.strip():
            failures.append(GateFailure(code="code_missing", message="Candidate did not provide Python source code."))
        else:
            try:
                ast.parse(code)
            except SyntaxError as exc:
                failures.append(
                    GateFailure(
                        code="syntax_error",
                        message=f"Python syntax error: {exc.msg}.",
                        details={"location": f"line {exc.lineno or 1}", "observed": exc.text or ""},
                    )
                )

        if task.family in {"humaneval", "humaneval_public"} and code.strip():
            entry_point = str(task.input_payload.get("entry_point", ""))
            if entry_point and not re.search(rf"^\s*def\s+{re.escape(entry_point)}\s*\(", code, re.MULTILINE):
                failures.append(
                    GateFailure(
                        code="entry_point_missing",
                        message=f"Candidate did not define the requested entry point: {entry_point}.",
                        details={"expected": entry_point, "observed": code[:240]},
                    )
                )
        if task.family == "ds1000" and code.strip() and not re.search(r"\bresult\s*=", code):
            failures.append(
                GateFailure(
                    code="result_assignment_missing",
                    message="Candidate code must assign the required result variable.",
                    details={"expected": "result = ...", "observed": code[:240]},
                )
            )

        return GateResult(gate_name=self.name, passed=not failures, score=0.0 if failures else 1.0, failures=failures)
