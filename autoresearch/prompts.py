from __future__ import annotations

import json
from typing import Any, Dict, List

from .models import ResearchPlan, ResearchTask, clamp_text

PROMPT_PREAMBLE = """You are running inside a code-as-harness research system.

Rules:
- Return only JSON matching the provided schema.
- Do not refer to hidden context or prior conversation.
- Do not modify files, call tools, or ask for more input.
- Be concise, explicit about uncertainty, and avoid invented citations.
- Treat this invocation as isolated; the harness will route artifacts.
"""


def _json_block(value: Any, max_chars: int = 9000) -> str:
    return clamp_text(json.dumps(value, indent=2, sort_keys=True), max_chars)


def principal_plan_prompt(plan: ResearchPlan, max_tasks: int) -> str:
    payload = {
        "plan": plan.to_dict(),
        "max_tasks": max_tasks,
        "worker_task_requirements": [
            "Each task must be independently answerable by one worker.",
            "Each task should be narrow enough to fit in a short LLM call.",
            "Do not create tasks that require hidden context from other workers.",
            "Prefer complementary lenses: methods, systems, evaluation, risks, and decision criteria.",
        ],
    }
    return f"""{PROMPT_PREAMBLE}

Role: principal researcher.

Create a bounded worker task graph for the research plan below. The output is not the final answer; it is a compact work order for leaf LLM worker actions.

Input:
{_json_block(payload)}
"""


def worker_prompt(plan: ResearchPlan, task: ResearchTask) -> str:
    payload = {
        "plan_brief": {
            "plan_id": plan.plan_id,
            "title": plan.title,
            "objective": plan.objective,
            "constraints": plan.constraints,
            "lenses": plan.lenses,
        },
        "assigned_task": task.to_dict(),
        "output_guidance": [
            "Focus only on the assigned task.",
            "Use compact, decision-useful claims.",
            "Use evidence_hint for remembered papers, systems, algorithms, or benchmarks when relevant.",
            "If you are unsure about a remembered detail, say so in uncertainties.",
        ],
    }
    return f"""{PROMPT_PREAMBLE}

Role: worker researcher ({task.worker_kind}).

Perform this leaf research action. You are not responsible for full synthesis; produce a compact artifact the principal can combine with other worker artifacts.

Input:
{_json_block(payload)}
"""


def synthesis_prompt(
    plan: ResearchPlan,
    task_plan: Dict[str, Any],
    worker_artifacts: List[Dict[str, Any]],
    max_chars: int,
) -> str:
    compact_workers = []
    for artifact in worker_artifacts:
        compact_workers.append(
            {
                "task_id": artifact.get("task_id"),
                "worker_kind": artifact.get("worker_kind"),
                "summary": artifact.get("summary"),
                "findings": artifact.get("findings", [])[:6],
                "assumptions": artifact.get("assumptions", [])[:6],
                "uncertainties": artifact.get("uncertainties", [])[:6],
                "confidence": artifact.get("confidence"),
            }
        )
    payload = {
        "plan": plan.to_dict(),
        "principal_task_brief": {
            "research_plan_id": task_plan.get("research_plan_id"),
            "synthesis_brief": task_plan.get("synthesis_brief"),
            "tasks": task_plan.get("tasks", []),
        },
        "worker_artifacts": compact_workers,
        "synthesis_requirements": [
            "Answer the original questions, not just the worker task titles.",
            "Call out conflicts, tradeoffs, and confidence limits.",
            "Prefer operational recommendations over generic advice.",
            "Do not claim external verification unless a worker artifact supports it.",
        ],
    }
    return f"""{PROMPT_PREAMBLE}

Role: principal researcher.

Synthesize the compact worker artifacts into the final research answer for this plan. You only receive artifacts, not worker transcripts, by design.

Input:
{_json_block(payload, max_chars=max_chars)}
"""
