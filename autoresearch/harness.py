from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .artifacts import ArtifactStore
from .llm import LLMProvider
from .models import ResearchPlan, ResearchTask, slugify
from .prompts import principal_plan_prompt, synthesis_prompt, worker_prompt
from .schemas import PLAN_SCHEMA, SYNTHESIS_SCHEMA, WORKER_SCHEMA


@dataclass
class HarnessConfig:
    output_dir: Path
    max_tasks: int = 4
    concurrency: int = 2
    synthesis_context_chars: int = 18000


class PrincipalResearcher:
    def __init__(self, provider: LLMProvider, config: HarnessConfig) -> None:
        self.provider = provider
        self.config = config

    def plan_tasks(self, plan: ResearchPlan, plan_dir: Path) -> Dict[str, Any]:
        max_tasks = max(1, min(self.config.max_tasks, plan.worker_budget))
        prompt = principal_plan_prompt(plan, max_tasks=max_tasks)
        (plan_dir / "principal_plan.prompt.md").write_text(prompt, encoding="utf-8")
        response = self.provider.generate_json(
            action=f"{slugify(plan.plan_id)}-principal-plan",
            prompt=prompt,
            schema=PLAN_SCHEMA,
            artifact_dir=plan_dir,
        )
        tasks = response.get("tasks", [])
        response["tasks"] = [ResearchTask.from_dict(item, idx).to_dict() for idx, item in enumerate(tasks)][
            :max_tasks
        ]
        if not response["tasks"]:
            raise ValueError(f"principal produced no tasks for {plan.plan_id}")
        return response

    def synthesize(
        self,
        plan: ResearchPlan,
        task_plan: Dict[str, Any],
        worker_artifacts: List[Dict[str, Any]],
        plan_dir: Path,
    ) -> Dict[str, Any]:
        prompt = synthesis_prompt(
            plan,
            task_plan,
            worker_artifacts,
            max_chars=self.config.synthesis_context_chars,
        )
        (plan_dir / "principal_synthesis.prompt.md").write_text(prompt, encoding="utf-8")
        response = self.provider.generate_json(
            action=f"{slugify(plan.plan_id)}-principal-synthesis",
            prompt=prompt,
            schema=SYNTHESIS_SCHEMA,
            artifact_dir=plan_dir,
        )
        response["plan_id"] = response.get("plan_id") or plan.plan_id
        return response


class WorkerPool:
    def __init__(self, provider: LLMProvider, config: HarnessConfig) -> None:
        self.provider = provider
        self.config = config

    def run_one(self, plan: ResearchPlan, task: ResearchTask, plan_dir: Path) -> Dict[str, Any]:
        workers_dir = plan_dir / "workers"
        workers_dir.mkdir(parents=True, exist_ok=True)
        prompt = worker_prompt(plan, task)
        (workers_dir / f"{task.task_id}.prompt.md").write_text(prompt, encoding="utf-8")
        response = self.provider.generate_json(
            action=f"{slugify(plan.plan_id)}-{task.task_id}",
            prompt=prompt,
            schema=WORKER_SCHEMA,
            artifact_dir=workers_dir,
        )
        response["task_id"] = response.get("task_id") or task.task_id
        response["worker_kind"] = response.get("worker_kind") or task.worker_kind
        return response

    def run_all(
        self,
        plan: ResearchPlan,
        tasks: List[ResearchTask],
        plan_dir: Path,
    ) -> List[Dict[str, Any]]:
        if self.config.concurrency <= 1 or len(tasks) == 1:
            return [self.run_one(plan, task, plan_dir) for task in tasks]

        results_by_id: Dict[str, Dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=self.config.concurrency) as executor:
            future_to_task = {
                executor.submit(self.run_one, plan, task, plan_dir): task for task in tasks
            }
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                results_by_id[task.task_id] = future.result()
        return [results_by_id[task.task_id] for task in tasks]


class AutoResearchHarness:
    def __init__(self, provider: LLMProvider, config: HarnessConfig) -> None:
        self.provider = provider
        self.config = config
        self.principal = PrincipalResearcher(provider, config)
        self.workers = WorkerPool(provider, config)

    def run(self, plans: List[ResearchPlan], label: str = "autoresearch") -> ArtifactStore:
        store = ArtifactStore.create(self.config.output_dir, label)
        store.write_json("input_plans.json", [plan.to_dict() for plan in plans])
        for plan in plans:
            self.run_plan(plan, store)
        store.flush_manifest()
        return store

    def run_plan(self, plan: ResearchPlan, store: ArtifactStore) -> Dict[str, Any]:
        plan_slug = slugify(plan.plan_id)
        plan_dir = store.plan_dir(plan.plan_id)
        store.write_json(f"{plan_slug}/plan.json", plan.to_dict())

        task_plan = self.principal.plan_tasks(plan, plan_dir)
        store.write_json(f"{plan_slug}/principal_plan.json", task_plan)
        tasks = [ResearchTask.from_dict(item, idx) for idx, item in enumerate(task_plan["tasks"])]
        store.write_json(f"{plan_slug}/tasks.json", [task.to_dict() for task in tasks])

        worker_results = self.workers.run_all(plan, tasks, plan_dir)
        for result in worker_results:
            task_id = slugify(str(result.get("task_id", "task")))
            store.write_json(f"{plan_slug}/workers/{task_id}.json", result)

        synthesis = self.principal.synthesize(plan, task_plan, worker_results, plan_dir)
        store.write_json(f"{plan_slug}/synthesis.json", synthesis)
        report = render_report(plan, task_plan, worker_results, synthesis)
        store.write_text(f"{plan_slug}/report.md", report, kind="markdown")
        return synthesis


def render_report(
    plan: ResearchPlan,
    task_plan: Dict[str, Any],
    worker_results: List[Dict[str, Any]],
    synthesis: Dict[str, Any],
) -> str:
    lines = [
        f"# {plan.title}",
        "",
        f"Plan ID: `{plan.plan_id}`",
        "",
        "## Objective",
        "",
        plan.objective,
        "",
        "## Executive Summary",
        "",
        synthesis.get("executive_summary", ""),
        "",
        "## Answer",
        "",
        synthesis.get("answer", ""),
        "",
        "## Findings By Question",
        "",
    ]
    for item in synthesis.get("findings_by_question", []):
        lines.extend(
            [
                f"### {item.get('question', 'Question')}",
                "",
                item.get("answer", ""),
                "",
                "Supporting worker tasks: "
                + ", ".join(f"`{task}`" for task in item.get("supporting_worker_tasks", [])),
                "",
            ]
        )
    lines.extend(["## Recommendations", ""])
    for item in synthesis.get("recommendations", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Conflicts Or Tensions", ""])
    for item in synthesis.get("conflicts_or_tensions", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Open Questions", ""])
    for item in synthesis.get("open_questions", []):
        lines.append(f"- {item}")
    lines.extend(["", f"Confidence: `{synthesis.get('confidence', 'unknown')}`", ""])
    lines.extend(["## Worker Artifacts", ""])
    for result in worker_results:
        lines.extend(
            [
                f"### {result.get('task_id', 'task')} ({result.get('worker_kind', 'worker')})",
                "",
                result.get("summary", ""),
                "",
            ]
        )
    lines.extend(
        [
            "## Harness Notes",
            "",
            f"Principal task brief: {task_plan.get('synthesis_brief', '')}",
            "",
            "This report was generated from compact JSON artifacts, not a cumulative chat transcript.",
            "",
        ]
    )
    return "\n".join(lines)
