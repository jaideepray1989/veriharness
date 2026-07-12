from __future__ import annotations

import json
from typing import Any, Dict

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


def _parse_answer(answer: str) -> Dict[str, Any]:
    try:
        data = json.loads(answer)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"text": answer}


class DeterministicGate:
    name = "deterministic"
    hard = True

    def evaluate(self, task: TaskSpec, output: LeafOutput, store: ArtifactStore, leaf_dir: str) -> GateResult:
        checks = task.hidden_oracle_payload.get("deterministic_checks", [])
        failures = []
        answer_data = _parse_answer(output.answer)
        for check in checks:
            kind = check.get("type")
            if kind == "expected_substring" and check.get("value", "") not in output.answer:
                failures.append(
                    GateFailure(code="expected_substring_missing", message=f"Missing substring: {check.get('value')}")
                )
            elif kind == "forbidden_substring" and check.get("value", "") in output.answer:
                failures.append(
                    GateFailure(code="forbidden_substring_present", message=f"Forbidden substring: {check.get('value')}")
                )
            elif kind == "json_field_equals":
                actual = answer_data.get(check.get("field"))
                if actual != check.get("value"):
                    failures.append(
                        GateFailure(
                            code="json_field_mismatch",
                            message=f"JSON field {check.get('field')} mismatch.",
                            details={"expected": check.get("value"), "actual": actual},
                        )
                    )
        return GateResult(gate_name=self.name, passed=not failures, score=0.0 if failures else 1.0, failures=failures)
