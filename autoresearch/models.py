from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "item"


def clamp_text(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 80].rstrip() + "\n\n[TRUNCATED BY HARNESS CONTEXT LIMIT]"


@dataclass
class ResearchPlan:
    plan_id: str
    title: str
    objective: str
    questions: List[str]
    constraints: List[str] = field(default_factory=list)
    lenses: List[str] = field(default_factory=list)
    worker_budget: int = 4

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResearchPlan":
        plan_id = str(data.get("id") or data.get("plan_id") or slugify(data["title"]))
        return cls(
            plan_id=plan_id,
            title=str(data["title"]),
            objective=str(data["objective"]),
            questions=[str(item) for item in data.get("questions", [])],
            constraints=[str(item) for item in data.get("constraints", [])],
            lenses=[str(item) for item in data.get("lenses", [])],
            worker_budget=int(data.get("worker_budget", 4)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def brief(self, max_chars: int = 5000) -> Dict[str, Any]:
        payload = self.to_dict()
        return json.loads(clamp_text(json.dumps(payload, indent=2), max_chars))


@dataclass
class ResearchTask:
    task_id: str
    title: str
    worker_kind: str
    question: str
    instructions: str
    expected_output: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], index: int) -> "ResearchTask":
        fallback_id = f"task-{index + 1}"
        return cls(
            task_id=slugify(str(data.get("task_id") or data.get("id") or fallback_id)),
            title=str(data.get("title") or f"Task {index + 1}"),
            worker_kind=str(data.get("worker_kind") or "research_worker"),
            question=str(data.get("question") or data.get("objective") or ""),
            instructions=str(data.get("instructions") or ""),
            expected_output=[str(item) for item in data.get("expected_output", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_plans(path: Path) -> List[ResearchPlan]:
    data = json.loads(path.read_text(encoding="utf-8"))
    raw_plans = data["plans"] if isinstance(data, dict) and "plans" in data else data
    if not isinstance(raw_plans, list):
        raise ValueError(f"{path} must contain a JSON list or an object with a 'plans' list")
    return [ResearchPlan.from_dict(item) for item in raw_plans]


def select_plans(
    plans: Sequence[ResearchPlan],
    selected_ids: Iterable[str],
    limit: int,
) -> List[ResearchPlan]:
    selected = [item for raw in selected_ids for item in raw.split(",") if item.strip()]
    if selected:
        selected_set = {slugify(item) for item in selected}
        plans = [plan for plan in plans if slugify(plan.plan_id) in selected_set]
        missing = selected_set - {slugify(plan.plan_id) for plan in plans}
        if missing:
            raise ValueError(f"unknown plan id(s): {', '.join(sorted(missing))}")
    if limit > 0:
        plans = list(plans)[:limit]
    return list(plans)
