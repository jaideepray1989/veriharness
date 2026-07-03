from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from veriharness.core.types import GateFailure, GateResult, LeafOutput, TaskSpec


def _answer_dict(output: LeafOutput) -> Dict[str, Any]:
    try:
        data = json.loads(output.answer)
        return data if isinstance(data, dict) else {"value": data}
    except Exception:
        return {"text": output.answer}


def evaluate_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    oracle_type = task.hidden_oracle_payload.get("oracle_type", task.family)
    if oracle_type == "context_trace":
        return context_trace_oracle(task, output)
    if oracle_type == "provenance_bias":
        return provenance_bias_oracle(task, output)
    if oracle_type == "mini_workflow":
        return mini_workflow_oracle(task, output)
    if oracle_type == "humaneval":
        return humaneval_oracle(task, output)
    if oracle_type == "boolq":
        return boolq_oracle(task, output)
    if oracle_type == "squad":
        return squad_oracle(task, output)
    if oracle_type == "multiple_choice":
        return multiple_choice_oracle(task, output)
    if oracle_type == "text_classification":
        return text_classification_oracle(task, output)
    return GateResult(gate_name="oracle", passed=False, score=0.0, failures=[
        GateFailure(code="unknown_oracle", message=f"No oracle for {oracle_type}")
    ])


def context_trace_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    data = _answer_dict(output)
    expected = task.hidden_oracle_payload.get("expected_export_format", "jsonl")
    forbidden = task.hidden_oracle_payload.get("forbidden_export_format", "csv")
    failures = []
    if data.get("export_format") != expected:
        failures.append(
            GateFailure(
                code="constraint_forgotten",
                message="Expected export format was not retained.",
                details={"expected": expected, "actual": data.get("export_format")},
            )
        )
    if data.get("export_format") == forbidden:
        failures.append(GateFailure(code="distractor_adopted", message="Forbidden export format was adopted."))
    fields = set(data.get("fields", []))
    if not {"id", "value"}.issubset(fields):
        failures.append(GateFailure(code="required_field_missing", message="Required fields missing."))
    return GateResult(gate_name="oracle", passed=not failures, score=0.0 if failures else 1.0, failures=failures)


def provenance_bias_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    data = _answer_dict(output)
    action = str(data.get("action", "")).lower()
    correct = set(task.hidden_oracle_payload.get("correct_actions", ["reject", "repair"]))
    failures = []
    if action not in correct:
        failures.append(
            GateFailure(
                code="wrong_own_claim_accepted" if task.input_payload.get("provenance_label") == "own_previous_answer" else "wrong_claim_accepted",
                message="Wrong claim was accepted or not repaired/rejected.",
                details={"action": action, "provenance_label": task.input_payload.get("provenance_label")},
            )
        )
    return GateResult(gate_name="oracle", passed=not failures, score=0.0 if failures else 1.0, failures=failures)


def mini_workflow_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    expected = task.hidden_oracle_payload.get("expected_substring", "")
    forbidden = task.hidden_oracle_payload.get("forbidden_substring", "")
    failures = []
    if expected and expected not in output.answer:
        failures.append(GateFailure(code="test_failed", message=f"Expected marker missing: {expected}"))
    if forbidden and f'"result": "{forbidden}"' in output.answer:
        failures.append(GateFailure(code="distractor_adopted", message=f"Forbidden value adopted: {forbidden}"))
    return GateResult(gate_name="oracle", passed=not failures, score=0.0 if failures else 1.0, failures=failures)


def humaneval_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    code = _candidate_code(output.answer)
    entry_point = str(task.hidden_oracle_payload.get("entry_point", ""))
    prompt = str(task.hidden_oracle_payload.get("prompt", ""))
    test = str(task.hidden_oracle_payload.get("test", ""))
    timeout = int(task.hidden_oracle_payload.get("timeout_seconds", 4))
    failures: List[GateFailure] = []

    if not code.strip():
        failures.append(GateFailure(code="code_missing", message="Candidate did not provide Python code."))
        return GateResult(gate_name="oracle", passed=False, score=0.0, failures=failures)

    solution = _assemble_humaneval_solution(prompt, code, entry_point)
    if entry_point and f"def {entry_point}" not in solution:
        failures.append(
            GateFailure(
                code="entry_point_missing",
                message=f"Candidate did not define or complete entry point: {entry_point}.",
            )
        )
        return GateResult(gate_name="oracle", passed=False, score=0.0, failures=failures)

    result = _run_humaneval_tests(solution, test, entry_point, timeout)
    if result["passed"]:
        return GateResult(gate_name="oracle", passed=True, score=1.0)
    failures.append(
        GateFailure(
            code=result["code"],
            message=result["message"],
            details={"stderr": result.get("stderr", "")[-1200:], "stdout": result.get("stdout", "")[-1200:]},
        )
    )
    return GateResult(gate_name="oracle", passed=False, score=0.0, failures=failures)


def boolq_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    expected = bool(task.hidden_oracle_payload.get("answer"))
    actual = _answer_bool(output.answer)
    if actual is expected:
        return GateResult(gate_name="oracle", passed=True, score=1.0)
    return GateResult(
        gate_name="oracle",
        passed=False,
        score=0.0,
        failures=[
            GateFailure(
                code="answer_mismatch",
                message="BoolQ answer did not match expected yes/no label.",
                details={"expected": expected, "actual": actual, "answer": output.answer[:400]},
            )
        ],
    )


def squad_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    expected_answers = [str(answer) for answer in task.hidden_oracle_payload.get("answers", [])]
    min_f1 = float(task.hidden_oracle_payload.get("min_f1", 0.8))
    actual = _answer_text(output.answer)
    best_f1 = max((_token_f1(actual, expected) for expected in expected_answers), default=0.0)
    exact = any(_normalize_answer(actual) == _normalize_answer(expected) for expected in expected_answers)
    if exact or best_f1 >= min_f1:
        return GateResult(gate_name="oracle", passed=True, score=1.0 if exact else best_f1)
    return GateResult(
        gate_name="oracle",
        passed=False,
        score=best_f1,
        failures=[
            GateFailure(
                code="answer_mismatch",
                message="SQuAD answer did not sufficiently match an accepted answer.",
                details={
                    "expected": expected_answers[:5],
                    "actual": actual[:400],
                    "best_f1": best_f1,
                    "min_f1": min_f1,
                },
            )
        ],
    )


def multiple_choice_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    expected_label = str(task.hidden_oracle_payload.get("answer_label", "")).strip()
    expected_text = str(task.hidden_oracle_payload.get("answer_text", "")).strip()
    labels = [
        str(choice.get("label", "")).strip()
        for choice in task.input_payload.get("choices", [])
        if isinstance(choice, dict)
    ]
    actual = _answer_choice(output.answer, labels)
    actual_label_ok = bool(expected_label) and _normalize_label(actual) == _normalize_label(expected_label)
    actual_text_ok = bool(expected_text) and _normalize_answer(actual) == _normalize_answer(expected_text)
    if actual_label_ok or actual_text_ok:
        return GateResult(gate_name="oracle", passed=True, score=1.0)
    return GateResult(
        gate_name="oracle",
        passed=False,
        score=0.0,
        failures=[
            GateFailure(
                code="answer_mismatch",
                message="Multiple-choice answer did not match the expected label or answer text.",
                details={
                    "expected_label": expected_label,
                    "expected_text": expected_text,
                    "actual": actual[:400],
                    "answer": output.answer[:400],
                },
            )
        ],
    )


def text_classification_oracle(task: TaskSpec, output: LeafOutput) -> GateResult:
    expected = str(task.hidden_oracle_payload.get("label", "")).strip()
    accepted = [str(label) for label in task.hidden_oracle_payload.get("accepted_labels", [])]
    actual = _answer_label(output.answer)
    if _label_matches(task, actual, expected):
        return GateResult(gate_name="oracle", passed=True, score=1.0)
    return GateResult(
        gate_name="oracle",
        passed=False,
        score=0.0,
        failures=[
            GateFailure(
                code="answer_mismatch",
                message="Classification label did not match expected label.",
                details={
                    "expected": expected,
                    "accepted_labels": accepted,
                    "actual": actual[:400],
                    "answer": output.answer[:400],
                },
            )
        ],
    )


def _candidate_code(answer: str) -> str:
    stripped = _strip_code_fences(answer.strip())
    if not stripped:
        return ""
    try:
        data = json.loads(stripped)
    except Exception:
        return stripped
    if isinstance(data, dict):
        for key in ["code", "completion", "solution", "answer"]:
            value = data.get(key)
            if isinstance(value, str):
                return _strip_code_fences(value.strip())
    if isinstance(data, str):
        return _strip_code_fences(data.strip())
    return stripped


def _answer_bool(answer: str) -> Optional[bool]:
    text = answer.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            value = data.get("answer")
        else:
            value = data
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            text = value
    except Exception:
        pass
    normalized = text.strip().lower()
    if normalized in {"true", "yes", "y"}:
        return True
    if normalized in {"false", "no", "n"}:
        return False
    return None


def _answer_text(answer: str) -> str:
    text = answer.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            value = data.get("answer", data.get("text", ""))
            return str(value).strip()
        if isinstance(data, str):
            return data.strip()
    except Exception:
        pass
    return _strip_code_fences(text)


def _answer_choice(answer: str, labels: List[str]) -> str:
    text = answer.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ["answer", "label", "choice", "choice_label"]:
                value = data.get(key)
                if value is not None:
                    text = str(value)
                    break
        elif isinstance(data, str):
            text = data
    except Exception:
        pass
    stripped = _strip_code_fences(text).strip()
    normalized_labels = {_normalize_label(label): label for label in labels}
    if _normalize_label(stripped) in normalized_labels:
        return normalized_labels[_normalize_label(stripped)]
    match = re.match(r"^\s*([A-Za-z0-9]+)\s*[\).:\]-]?\s+", stripped)
    if match and _normalize_label(match.group(1)) in normalized_labels:
        return normalized_labels[_normalize_label(match.group(1))]
    return stripped


def _answer_label(answer: str) -> str:
    text = answer.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ["label", "answer", "class", "classification"]:
                value = data.get(key)
                if value is not None:
                    return str(value).strip()
        if isinstance(data, str):
            return data.strip()
    except Exception:
        pass
    return _strip_code_fences(text).strip()


def _label_matches(task: TaskSpec, actual: str, expected: str) -> bool:
    actual_norm = _normalize_label(actual)
    candidates = [expected]
    aliases = task.hidden_oracle_payload.get("accepted_aliases", {})
    if isinstance(aliases, dict):
        for label, values in aliases.items():
            if _normalize_label(str(label)) != _normalize_label(expected):
                continue
            if isinstance(values, list):
                candidates.extend(str(value) for value in values)
            else:
                candidates.append(str(values))
    descriptions = task.input_payload.get("label_descriptions", {})
    if isinstance(descriptions, dict):
        for label, description in descriptions.items():
            if _normalize_label(str(label)) == _normalize_label(expected):
                candidates.append(str(description))
    return any(actual_norm == _normalize_label(candidate) for candidate in candidates)


def _normalize_answer(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\b(a|an|the)\b", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


def _normalize_label(text: str) -> str:
    normalized = _strip_code_fences(str(text)).strip().strip("\"'")
    normalized = re.sub(r"^(answer|label|class|classification)\s*[:=\-]\s*", "", normalized, flags=re.I)
    normalized = normalized.lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def _token_f1(prediction: str, ground_truth: str) -> float:
    pred_tokens = _normalize_answer(prediction).split()
    truth_tokens = _normalize_answer(ground_truth).split()
    if not pred_tokens or not truth_tokens:
        return 1.0 if pred_tokens == truth_tokens else 0.0
    common = 0
    truth_counts: Dict[str, int] = {}
    for token in truth_tokens:
        truth_counts[token] = truth_counts.get(token, 0) + 1
    for token in pred_tokens:
        count = truth_counts.get(token, 0)
        if count:
            common += 1
            truth_counts[token] = count - 1
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall = common / len(truth_tokens)
    return 2 * precision * recall / (precision + recall)


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _assemble_humaneval_solution(prompt: str, code: str, entry_point: str) -> str:
    if entry_point and f"def {entry_point}" in code:
        return code
    return prompt.rstrip() + "\n" + textwrap.indent(code.strip(), "    ") + "\n"


def _run_humaneval_tests(solution: str, test: str, entry_point: str, timeout: int) -> Dict[str, Any]:
    runner = "\n".join(
        [
            "import faulthandler",
            "faulthandler.enable()",
            _humaneval_import_prelude(),
            solution,
            test,
            f"check({entry_point})",
            "",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="veriharness_humaneval_") as tmp_dir:
        script = Path(tmp_dir) / "candidate.py"
        script.write_text(runner, encoding="utf-8")
        try:
            completed = subprocess.run(
                [sys.executable, str(script)],
                cwd=tmp_dir,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "passed": False,
                "code": "timeout",
                "message": f"HumanEval tests timed out after {timeout}s.",
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }
    if completed.returncode == 0:
        return {"passed": True}
    stderr = completed.stderr or ""
    if "SyntaxError" in stderr or "IndentationError" in stderr:
        code = "syntax_error"
    elif "AssertionError" in stderr:
        code = "unit_test_failed"
    else:
        code = "runtime_error"
    return {
        "passed": False,
        "code": code,
        "message": _humaneval_failure_message(stderr)
        or f"HumanEval subprocess failed with exit code {completed.returncode}.",
        "stdout": completed.stdout or "",
        "stderr": stderr,
    }


def _last_error_line(stderr: str) -> str:
    for line in reversed(stderr.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _humaneval_failure_message(stderr: str) -> str:
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    for line in reversed(lines):
        if line.startswith("assert "):
            return line
    return _last_error_line(stderr)


def _humaneval_import_prelude() -> str:
    return "\n".join(
        [
            "import collections",
            "import copy",
            "import datetime",
            "import functools",
            "import hashlib",
            "import heapq",
            "import itertools",
            "import math",
            "import re",
            "import string",
            "import sys",
            "from typing import *",
            "try:",
            "    import numpy as np",
            "except Exception:",
            "    np = None",
            "",
        ]
    )
