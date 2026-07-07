from __future__ import annotations

from typing import Any, Dict, List

from veriharness.core.types import BudgetConfig, ContextPack, HarnessVariant, TaskSpec
from veriharness.leaves.output_schemas import leaf_output_schema


def _summary_from_trace(trace: List[str]) -> str:
    if not trace:
        return ""
    return " | ".join([trace[0], trace[len(trace) // 2], trace[-1]])


def build_context_pack(
    task: TaskSpec,
    variant: HarnessVariant,
    budget: BudgetConfig,
    retry_feedback: List[str] | None = None,
) -> ContextPack:
    payload = task.input_payload
    accepted = list(payload.get("accepted_facts", []))
    rejected = list(payload.get("rejected_facts", []))
    constraints = list(payload.get("constraints", []))
    distractors = list(payload.get("distractors", []))
    current_state: Dict[str, Any] = {"task_family": task.family}

    if task.family == "context_trace":
        trace = list(payload.get("raw_trace", []))
        if variant == HarnessVariant.H0:
            current_state["raw_trace"] = trace
            distractors.extend(payload.get("trace_distractors", []))
        elif variant == HarnessVariant.H1:
            current_state["summarized_trace"] = _summary_from_trace(trace)
            distractors.extend(payload.get("trace_distractors", [])[:1])
        else:
            accepted.append("Active invariant: export_format must be jsonl.")
            rejected.append("Reject distractor: export_format must not be csv.")
            current_state["objective_payload"] = {
                "requested_fields": payload.get("required_fields", []),
                "format": "jsonl",
            }
    elif task.family == "provenance_bias":
        current_state.update(
            {
                "provenance_label": payload.get("provenance_label"),
                "claim_to_audit": payload.get("wrong_claim"),
                "ground_truth_hint": payload.get("ground_truth")
                if variant.uses_external_gates or variant.uses_state_context
                else None,
            }
        )
        constraints.append("Audit the claim; accept only if it matches ground truth.")
        if variant.uses_state_context:
            rejected.append(f"Reject wrong claim: {payload.get('wrong_claim')}")
            accepted.append(f"Ground truth: {payload.get('ground_truth')}")
    elif task.family == "humaneval":
        prompt = payload.get("prompt", "")
        entry_point = payload.get("entry_point", "")
        constraints.extend(
            [
                "Return executable Python source code.",
                f"The solution must define or complete the entry point: {entry_point}.",
                "Do not include markdown fences in the answer field.",
            ]
        )
        if variant == HarnessVariant.H0:
            current_state["raw_benchmark_record"] = {
                "source_task_id": payload.get("source_task_id"),
                "prompt": prompt,
                "entry_point": entry_point,
            }
        elif variant == HarnessVariant.H1:
            current_state["summarized_problem"] = prompt
            current_state["entry_point"] = entry_point
        else:
            current_state["problem_prompt"] = prompt
            current_state["entry_point"] = entry_point
            accepted.append(f"Implement the HumanEval entry point: {entry_point}.")
            accepted.append("Output should be a Python module that can be saved as solution.py.")
    elif task.family == "swebench_patch":
        current_state["repo"] = payload.get("repo", "")
        current_state["instance_id"] = payload.get("instance_id", "")
        current_state["base_commit"] = payload.get("base_commit", "")
        current_state["problem_statement"] = payload.get("problem_statement", "")
        current_state["hints_text"] = payload.get("hints_text", "")
        current_state["fail_to_pass"] = payload.get("fail_to_pass", [])
        current_state["pass_to_pass"] = payload.get("pass_to_pass", [])
        constraints.extend(
            [
                "Return a unified diff patch only in the answer field.",
                "Patch paths must be relative to the repository root.",
                "List patch.diff in artifacts.",
            ]
        )
        accepted.append("SWE-bench scoring requires the official containerized test harness.")
    elif task.family == "ds1000":
        current_state["prompt"] = payload.get("prompt", "")
        current_state["library"] = payload.get("library", "")
        current_state["problem_id"] = payload.get("problem_id", "")
        constraints.extend(
            [
                "Return Python code that sets a variable named result.",
                "Do not include markdown fences in the answer field.",
                "List solution.py in artifacts.",
            ]
        )
        accepted.append("DS-1000 code is executed in the benchmark-provided test context.")
    elif task.family == "mlagentbench":
        current_state["task_name"] = payload.get("task_name", "")
        current_state["research_problem"] = payload.get("research_problem", "")
        current_state["upstream_repo"] = payload.get("upstream_repo", "")
        current_state["benchmark_path"] = payload.get("benchmark_path", "")
        constraints.extend(
            [
                "Return a JSON research plan in the answer field.",
                "Name train and evaluation commands.",
                "List research_plan.json in artifacts.",
            ]
        )
        accepted.append("Paper-quality MLAgentBench scoring must run the upstream runner and eval scripts.")
    elif task.family in {"boolq", "squad"}:
        current_state["question"] = payload.get("question", "")
        current_state["passage"] = payload.get("passage", "")
        current_state["title"] = payload.get("title", "")
        constraints.append("Answer using only the provided passage.")
        constraints.append("Return a compact JSON object in the LeafOutput.answer field.")
        if task.family == "boolq":
            constraints.append('Answer JSON must look like {"answer": true} or {"answer": false}.')
            accepted.append("BoolQ is a yes/no reading comprehension task.")
        else:
            constraints.append('Answer JSON must look like {"answer": "short span from passage"}.')
            accepted.append("SQuAD is an extractive question answering task.")
    elif task.family == "multiple_choice":
        current_state["benchmark_name"] = payload.get("benchmark_name", "")
        current_state["question"] = payload.get("question", "")
        current_state["support"] = payload.get("support", "")
        current_state["choices"] = payload.get("choices", [])
        constraints.append("Select exactly one visible choice label.")
        constraints.append('Answer JSON must look like {"answer": "A"} using one listed label.')
        accepted.append("Multiple-choice tasks must be answered from the visible choices only.")
    elif task.family == "text_classification":
        current_state["benchmark_name"] = payload.get("benchmark_name", "")
        for field in ["text", "sentence", "sentence1", "sentence2"]:
            if field in payload:
                current_state[field] = payload.get(field)
        current_state["labels"] = payload.get("labels", [])
        if "label_descriptions" in payload:
            current_state["label_descriptions"] = payload.get("label_descriptions", {})
        constraints.append("Return exactly one label from the visible label set.")
        constraints.append('Answer JSON must look like {"label": "<one visible label>"} using no extra keys.')
        accepted.append("Text classification tasks must use only the supplied label vocabulary.")
    else:
        current_state["workflow"] = payload.get("workflow")
        current_state["visible_instruction"] = payload.get("visible_instruction")
        if variant == HarnessVariant.H0:
            current_state["raw_trace"] = payload.get("raw_trace", [])
        elif variant == HarnessVariant.H1:
            current_state["summarized_trace"] = _summary_from_trace(payload.get("raw_trace", []))
        else:
            accepted.extend(payload.get("invariants", []))
            rejected.extend(payload.get("wrong_docs", []))

    if retry_feedback:
        current_state["retry_feedback"] = retry_feedback

    return ContextPack(
        task_id=task.task_id,
        variant=variant.value,
        objective=task.description,
        current_state=current_state,
        accepted_facts=accepted,
        rejected_facts=rejected,
        constraints=constraints,
        distractors=distractors,
        output_schema=leaf_output_schema(),
        budget=budget.model_dump(),
    )


def context_pack_to_markdown(pack: ContextPack) -> str:
    lines = [
        f"# Context Pack: {pack.task_id}",
        "",
        f"Variant: {pack.variant}",
        "",
        "## Objective",
        pack.objective,
        "",
        "## Current State",
        "```json",
        pack.model_dump_json(indent=2),
        "```",
    ]
    return "\n".join(lines) + "\n"
