from __future__ import annotations

from veriharness.core.types import LeafRequest


def render_leaf_prompt(request: LeafRequest) -> str:
    family_guidance = _family_guidance(request)
    attempt_guidance = _attempt_guidance(request)
    repair_guidance = _repair_guidance(request)
    return f"""You are a bounded worker.

You do not decide final acceptance.
Return only the requested structured output.
List claims explicitly.
List artifacts explicitly.
State risks separately from the answer.
Do not include markdown fences.
Do not include explanatory text outside the JSON object.

{family_guidance}

{attempt_guidance}

{repair_guidance}

Context pack:
{request.context_pack.model_dump_json(indent=2)}
"""


def _family_guidance(request: LeafRequest) -> str:
    family = request.task.family
    if family == "context_trace":
        return """For this context_trace task:
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look like {"export_format":"jsonl","fields":["id","value"]}.
- The fields array is mandatory; do not omit it.
- List "answer.json" in artifacts."""
    if family == "provenance_bias":
        return """For this provenance_bias task:
- Audit the claim against the provided context.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look like {"action":"reject","claim":"..."} or {"action":"repair","claim":"..."}.
- List "audit.json" in artifacts."""
    if family == "mini_workflow":
        return """For this mini_workflow task:
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look like {"result":"expected_marker","artifact":"workflow_patch.txt"}.
- List "workflow_patch.txt" in artifacts."""
    if family == "humaneval":
        prompt = str(request.task.input_payload.get("prompt", "")).rstrip()
        entry_point = str(request.task.input_payload.get("entry_point", ""))
        return f"""For this humaneval task:
- Solve the Python programming problem in the context pack.
- The LeafOutput.answer field must be a string containing Python source code.
- Prefer a complete function definition for the requested entry point.
- Implement the actual semantics in the docstring, not only the examples.
- Before finalizing, mentally run edge cases and the examples.
- Do not include markdown fences inside the answer field.
- List "solution.py" in artifacts.

Requested entry point: {entry_point}

Official HumanEval prompt:
{prompt}"""
    if family == "swebench_patch":
        return """For this swebench_patch task:
- Read the GitHub issue statement, hints, repo, and base commit in the context pack.
- The LeafOutput.answer field must be a unified diff patch string.
- Do not include markdown fences inside the answer field.
- List "patch.diff" in artifacts.
- This local harness checks patch structure/reference overlap only; official SWE-bench scoring must run separately."""
    if family == "ds1000":
        return """For this ds1000 task:
- Solve the data-science coding problem in the context pack.
- The LeafOutput.answer field must be Python code.
- The code must set a variable named result.
- Do not include markdown fences inside the answer field.
- List "solution.py" in artifacts."""
    if family == "mlagentbench":
        return """For this mlagentbench task:
- Read the ML research problem in the context pack.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must include task_name, train_command, eval_command, and expected_artifacts.
- List "research_plan.json" in artifacts.
- Official scoring must run the upstream MLAgentBench runner and eval scripts."""
    if family == "boolq":
        return """For this boolq task:
- Read the passage and question in the context pack.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look exactly like {"answer":true} or {"answer":false}.
- Use only the passage; do not rely on outside knowledge.
- List "answer.json" in artifacts."""
    if family == "squad":
        return """For this squad task:
- Read the passage and question in the context pack.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look exactly like {"answer":"short answer span"}.
- Prefer the shortest answer phrase from the passage that answers the question.
- List "answer.json" in artifacts."""
    if family == "multiple_choice":
        return """For this multiple_choice task:
- Read the question, support, and visible choices in the context pack.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look exactly like {"answer":"A"} using one listed choice label.
- Do not invent a new option or answer with more than one label.
- List "answer.json" in artifacts."""
    if family == "text_classification":
        return """For this text_classification task:
- Read the provided text or sentence pair and the visible label set.
- The LeafOutput.answer field must itself be a JSON string.
- That answer JSON must look exactly like {"label":"<one visible label>"}.
- Use exactly one label from the supplied label vocabulary.
- List "answer.json" in artifacts."""
    return "The LeafOutput.answer field should contain the task answer as compact JSON where possible."


def _attempt_guidance(request: LeafRequest) -> str:
    candidate_index = _candidate_index(request.candidate_id)
    if request.task.family == "multiple_choice":
        strategies = [
            "Use a direct evidence-matching strategy: identify the phrase or fact in the question/support that matches one choice.",
            "Use elimination: reject each visibly wrong choice before selecting the remaining best label.",
            "Use answer-type checking: decide what type of entity/process/value is needed, then match that to one choice.",
            "Use a counterfactual check: compare the top two labels and select the one that best satisfies the full question.",
        ]
        return _strategy_guidance(request, strategies[candidate_index % len(strategies)])
    if request.task.family == "text_classification":
        benchmark = str(request.task.input_payload.get("benchmark_name", ""))
        if benchmark == "trec_qc":
            strategies = [
                "Classify by the expected answer type: person, place, number, entity, description, or abbreviation.",
                "Rewrite the question as 'the answer should be a ...' and map that answer type to exactly one label.",
                "Eliminate labels whose answer type cannot satisfy the question before choosing the closest label.",
                "Check whether the question asks for a definition/description before choosing an entity/person/location/number label.",
            ]
        else:
            strategies = [
                "Use the literal label definitions and choose the single label best supported by the text.",
                "Try the negative label first: look for contradiction, non-entailment, non-equivalence, or negative sentiment before accepting the positive label.",
                "Try the positive label first: look for entailment, equivalence, or positive sentiment, then reject only if unsupported.",
                "Compare both labels explicitly and choose the one with stronger textual evidence.",
            ]
        return _strategy_guidance(request, strategies[candidate_index % len(strategies)])
    if request.task.family != "humaneval":
        return ""
    strategies = [
        "Use a direct, simple implementation that follows the docstring literally.",
        "Use an edge-case-first implementation; avoid assumptions such as sorted input, adjacency, or non-empty data unless the prompt states them.",
        "Use a brute-force/reference implementation when input sizes are unspecified; prioritize correctness over cleverness.",
        "Use a type-robust implementation that handles empty strings/lists, duplicates, and boundary values.",
    ]
    return _strategy_guidance(request, strategies[candidate_index % len(strategies)])


def _strategy_guidance(request: LeafRequest, strategy: str) -> str:
    return f"""Attempt metadata:
- attempt: {request.attempt}
- candidate: {request.candidate_id}
- candidate strategy: {strategy}
- Do not repeat a previous failing answer when repair feedback is present."""


def _repair_guidance(request: LeafRequest) -> str:
    feedback = request.retry_feedback or request.context_pack.current_state.get("retry_feedback", [])
    if not feedback:
        return ""
    bullets = "\n".join(f"- {item}" for item in feedback)
    return f"""Repair guidance from external gates:
{bullets}
- Treat every repair item as a hard requirement for this attempt.
- For code repairs, change the algorithm when the failure is semantic; do not merely reformat the same code.
- If a failing assert is shown, identify which behavior it demands and update the implementation to satisfy that case and the general rule behind it.
- Return the full LeafOutput JSON object again, not only the nested answer JSON."""


def _candidate_index(candidate_id: str) -> int:
    try:
        return int(candidate_id.rsplit("-", 1)[1])
    except Exception:
        return 0
