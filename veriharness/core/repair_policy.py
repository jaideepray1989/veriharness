from __future__ import annotations

from typing import Iterable, List

from veriharness.core.types import ContextPack, GateResult, LeafOutput, TaskSpec

_FAILURE_PRIORITY = [
    "client_error",
    "schema_invalid",
    "empty_answer",
    "task_id_mismatch",
    "artifact_missing",
    "claim_without_evidence",
    "entry_point_missing",
    "code_missing",
    "syntax_error",
    "timeout",
    "runtime_error",
    "unit_test_failed",
    "expected_substring_missing",
    "forbidden_substring_present",
    "json_field_mismatch",
    "constraint_forgotten",
    "distractor_adopted",
    "required_field_missing",
    "wrong_own_claim_accepted",
    "wrong_claim_accepted",
    "answer_mismatch",
    "test_failed",
]


def build_retry_feedback(
    task: TaskSpec,
    context: ContextPack,
    output: LeafOutput,
    gate_results: List[GateResult],
) -> List[str]:
    """Convert gate failures into visible, task-conditioned repair guidance."""
    feedback: List[str] = []

    def add(item: str) -> None:
        if item and item not in feedback:
            feedback.append(item)

    failures = [failure for result in gate_results for failure in result.failures]
    if not failures:
        return []

    add("Previous attempt failed external gates. Return a corrected complete LeafOutput JSON object.")
    add("Do not add prose or markdown fences; the entire response must be one valid JSON object.")
    for result in gate_results:
        for failure in result.failures:
            add(f"{result.gate_name}.{failure.code}: {failure.message}")

    failure_codes = {failure.code for failure in failures}
    if {"schema_invalid", "empty_answer", "task_id_mismatch"} & failure_codes:
        add("Preserve the exact task_id, include a non-empty answer string, and satisfy the LeafOutput schema.")
    if "artifact_missing" in failure_codes:
        add(f"List and produce the required artifact for this task family: {required_artifact_for(task)}.")
    if "claim_without_evidence" in failure_codes:
        add("Include at least one explicit claim with an evidence_refs entry pointing to the context pack.")

    if task.family == "context_trace":
        requested_fields = _requested_fields(task, context)
        add(
            "The answer field must be a JSON-encoded string like "
            f"{{\"export_format\":\"jsonl\",\"fields\":{requested_fields}}}."
        )
        add("Use the active invariant from accepted_facts/constraints; do not use rejected or distractor CSV guidance.")
        if "required_field_missing" in failure_codes:
            add(f"Include all required fields in the answer JSON: {', '.join(requested_fields)}.")
        if {"constraint_forgotten", "distractor_adopted", "json_field_mismatch"} & failure_codes:
            add("Set export_format to jsonl unless the visible context contains a newer accepted invariant.")
    elif task.family == "provenance_bias":
        add(
            "The answer field must be a JSON-encoded string like "
            "{\"action\":\"reject\",\"claim\":\"...\"} or {\"action\":\"repair\",\"claim\":\"...\"}; "
            "do not answer with a bare word."
        )
        add("Do not choose action=accept for a disputed claim unless it matches the visible ground truth.")
        ground_truth = context.current_state.get("ground_truth_hint")
        if ground_truth:
            add(f"If repairing, use the visible ground truth claim: {ground_truth}")
        if {"wrong_claim_accepted", "wrong_own_claim_accepted"} & failure_codes:
            add("Choose action=reject or action=repair, and keep the rejected wrong claim separate from the repaired claim.")
    elif task.family == "mini_workflow":
        add(
            "The answer field must be a JSON-encoded string like "
            "{\"result\":\"<expected_marker>\",\"artifact\":\"workflow_patch.txt\"}."
        )
        marker = _accepted_marker(context)
        if marker:
            add(f"Use the expected marker from accepted_facts as the result value: {marker}")
        add("Do not use legacy CSV defaults or wrong_docs as the final result.")
    elif task.family == "humaneval":
        entry_point = str(task.input_payload.get("entry_point", ""))
        add("The answer field must contain Python source code, not prose or markdown.")
        add(f"Define or complete the requested HumanEval entry point: {entry_point}.")
        add('List "solution.py" in artifacts so the candidate can be preserved and tested.')
        if "entry_point_missing" in failure_codes:
            add(f"Add a function definition for {entry_point} with the signature implied by the prompt.")
        if "code_missing" in failure_codes:
            add("Return actual Python code in LeafOutput.answer.")
        if "syntax_error" in failure_codes:
            add("Fix Python syntax/indentation and ensure the module imports cleanly.")
        if "timeout" in failure_codes:
            add("Simplify the algorithm and avoid unbounded loops or exponential brute force.")
        if {"unit_test_failed", "runtime_error"} & failure_codes:
            add("Revise the implementation to satisfy edge cases implied by the prompt and gate error.")
    elif task.family == "boolq":
        add('The answer field must be a JSON-encoded string like {"answer":true} or {"answer":false}.')
        add("Re-read the passage and answer only the yes/no question asked; ignore outside knowledge.")
        if "answer_mismatch" in failure_codes:
            add("The previous boolean was rejected. Re-evaluate whether the passage entails yes or no.")
    elif task.family == "squad":
        add('The answer field must be a JSON-encoded string like {"answer":"short answer span"}.')
        add("Choose the shortest passage span that directly answers the question.")
        if "answer_mismatch" in failure_codes:
            add("The previous span did not match accepted answers closely enough; use a shorter, more exact phrase from the passage.")
    elif task.family == "multiple_choice":
        labels = _visible_choice_labels(task)
        add('The answer field must be a JSON-encoded string like {"answer":"A"}.')
        if labels:
            add(f"Choose exactly one of these visible choice labels: {', '.join(labels)}.")
        if "answer_mismatch" in failure_codes:
            add("The previous choice was rejected; re-evaluate the question and choose a different visible label if needed.")
    elif task.family == "text_classification":
        labels = [str(label) for label in task.input_payload.get("labels", [])]
        add('The answer field must be a JSON-encoded string like {"label":"<one visible label>"}.')
        if labels:
            add(f"Use exactly one of these labels: {', '.join(labels)}.")
        if "answer_mismatch" in failure_codes:
            add("The previous classification label was rejected; compare the text against the full label vocabulary again.")

    if output.answer:
        add(f"Previous answer was rejected: {output.answer[:240]}")
    return feedback


def build_natural_retry_feedback(
    _task: TaskSpec,
    _context: ContextPack,
    output: LeafOutput,
    gate_results: List[GateResult],
) -> List[str]:
    """Return untyped natural-language gate feedback.

    This intentionally avoids machine-readable failure codes such as
    ``artifact_missing`` or ``evidence.claim_without_evidence``. It is useful as
    a baseline for "more information" without typed repair structure.
    """
    feedback: List[str] = []

    def add(item: str) -> None:
        if item and item not in feedback:
            feedback.append(item)

    failures = [failure for result in gate_results for failure in result.failures]
    if not failures:
        return []

    add("The previous attempt failed external checks. Revise it and return one complete LeafOutput JSON object.")
    for result in gate_results:
        for failure in result.failures:
            gate_label = result.gate_name.replace("_", " ")
            add(f"The {gate_label} check reported: {_sanitize_message(failure.message)}")
    if output.answer:
        add(f"The previous answer was rejected: {output.answer[:240]}")
    return feedback


def build_targeted_untyped_feedback(
    task: TaskSpec,
    context: ContextPack,
    output: LeafOutput,
    gate_results: List[GateResult],
) -> List[str]:
    """Return natural-language repair guidance for the highest-priority locus.

    This isolates target selection from typed payloads: the policy chooses a
    deterministic locus by priority, but it does not expose gate names, failure
    codes, or code-like payloads to the leaf.
    """
    failures = [failure for result in gate_results for failure in result.failures]
    if not failures:
        return []
    target_codes = _primary_failure_codes(failure.code for failure in failures)
    feedback: List[str] = [
        "The previous attempt failed external checks. Focus on the highest-priority issue below.",
    ]

    if {"client_error", "schema_invalid", "empty_answer", "task_id_mismatch"} & target_codes:
        feedback.extend(
            [
                "Focus first on producing one valid LeafOutput JSON object with the exact task id.",
                "The answer must be non-empty and must not include prose or markdown outside the JSON object.",
            ]
        )
    elif "artifact_missing" in target_codes:
        feedback.append(f"Focus first on listing and producing the required artifact: {required_artifact_for(task)}.")
    elif "claim_without_evidence" in target_codes:
        feedback.append("Focus first on adding an explicit claim with a concrete evidence reference from the context.")
    elif {"entry_point_missing", "code_missing", "syntax_error", "timeout", "runtime_error", "unit_test_failed"} & target_codes:
        feedback.extend(_code_target_guidance(task, target_codes))
    elif {
        "expected_substring_missing",
        "forbidden_substring_present",
        "json_field_mismatch",
        "constraint_forgotten",
        "distractor_adopted",
        "required_field_missing",
        "test_failed",
    } & target_codes:
        feedback.extend(_deterministic_target_guidance(task, context, target_codes))
    elif {"wrong_own_claim_accepted", "wrong_claim_accepted"} & target_codes:
        feedback.extend(
            [
                "Focus first on rejecting or repairing the disputed claim instead of accepting it.",
                "Keep the disputed claim separate from the corrected claim.",
            ]
        )
    elif "answer_mismatch" in target_codes:
        feedback.extend(_answer_target_guidance(task))
    else:
        feedback.append("Focus first on correcting the answer so that it satisfies the visible task constraints.")

    if output.answer:
        feedback.append(f"The previous answer was rejected: {output.answer[:240]}")
    return _dedupe(feedback)


def required_artifact_for(task: TaskSpec) -> str:
    if task.family == "context_trace":
        return "answer.json"
    if task.family == "provenance_bias":
        return "audit.json"
    if task.family == "mini_workflow":
        return "workflow_patch.txt"
    if task.family == "humaneval":
        return "solution.py"
    if task.family in {"boolq", "squad", "multiple_choice", "text_classification"}:
        return "answer.json"
    return "the artifact named in the task guidance"


def _requested_fields(task: TaskSpec, context: ContextPack) -> List[str]:
    objective_payload = context.current_state.get("objective_payload", {})
    fields = objective_payload.get("requested_fields") or task.input_payload.get("required_fields") or ["id", "value"]
    return [str(field) for field in fields]


def _accepted_marker(context: ContextPack) -> str:
    prefix = "Expected result marker:"
    for fact in context.accepted_facts:
        if prefix in fact:
            return fact.split(prefix, 1)[1].strip()
    return ""


def _visible_choice_labels(task: TaskSpec) -> List[str]:
    labels: List[str] = []
    for choice in task.input_payload.get("choices", []):
        if isinstance(choice, dict) and choice.get("label") is not None:
            labels.append(str(choice["label"]))
    return labels


def _primary_failure_codes(codes: Iterable[str]) -> set[str]:
    present = {str(code) for code in codes}
    for code in _FAILURE_PRIORITY:
        if code in present:
            return {code}
    return present


def _sanitize_message(message: str) -> str:
    sanitized = str(message).replace("_", " ")
    for code in _FAILURE_PRIORITY:
        sanitized = sanitized.replace(code, code.replace("_", " "))
    return sanitized


def _dedupe(items: List[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def _code_target_guidance(task: TaskSpec, target_codes: set[str]) -> List[str]:
    entry_point = str(task.input_payload.get("entry_point", ""))
    guidance = [
        "Focus first on returning executable Python source code rather than prose.",
        f"The code must define the requested entry point: {entry_point}.",
        'List "solution.py" in artifacts.',
    ]
    if "syntax_error" in target_codes:
        guidance.append("Fix Python syntax and indentation before changing semantics.")
    if "timeout" in target_codes:
        guidance.append("Avoid unbounded loops or algorithms that scale explosively.")
    if {"runtime_error", "unit_test_failed"} & target_codes:
        guidance.append("Change the algorithm to satisfy the failing behavior, including edge cases.")
    return guidance


def _deterministic_target_guidance(task: TaskSpec, context: ContextPack, target_codes: set[str]) -> List[str]:
    if task.family == "context_trace":
        requested_fields = _requested_fields(task, context)
        guidance = [
            "Focus first on preserving the active invariant from the current context.",
            "Use jsonl as the export format unless a newer accepted invariant is visible.",
            f"Include these required fields: {', '.join(requested_fields)}.",
        ]
    elif task.family == "mini_workflow":
        marker = _accepted_marker(context)
        guidance = [
            "Focus first on using the expected workflow marker from accepted facts.",
            'The answer JSON should include result and artifact fields, with artifact set to "workflow_patch.txt".',
        ]
        if marker:
            guidance.append(f"Use this expected marker as the result value: {marker}")
    else:
        guidance = ["Focus first on satisfying the deterministic checks from the visible constraints."]
    if "forbidden_substring_present" in target_codes or "distractor_adopted" in target_codes:
        guidance.append("Do not use rejected or distractor values as the final answer.")
    return guidance


def _answer_target_guidance(task: TaskSpec) -> List[str]:
    if task.family == "boolq":
        return [
            'Return the answer as {"answer": true} or {"answer": false}.',
            "Re-read the passage and decide whether it entails yes or no.",
        ]
    if task.family == "squad":
        return [
            'Return the answer as {"answer": "short answer span"}.',
            "Use the shortest passage span that directly answers the question.",
        ]
    if task.family == "multiple_choice":
        labels = _visible_choice_labels(task)
        guidance = ['Return exactly one visible choice as {"answer": "A"}.']
        if labels:
            guidance.append(f"Choose one of these visible labels: {', '.join(labels)}.")
        return guidance
    if task.family == "text_classification":
        labels = [str(label) for label in task.input_payload.get("labels", [])]
        guidance = ['Return exactly one visible label as {"label": "<label>"}.']
        if labels:
            guidance.append(f"Choose one of these labels: {', '.join(labels)}.")
        return guidance
    return ["Focus first on changing the final answer, not only the formatting."]
