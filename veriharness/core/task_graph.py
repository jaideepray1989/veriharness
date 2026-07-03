from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from veriharness.core.types import TaskSpec


@dataclass
class TaskGraph:
    tasks: Dict[str, TaskSpec] = field(default_factory=dict)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)

    def add_task(self, task: TaskSpec, depends_on: List[str] | None = None) -> None:
        self.tasks[task.task_id] = task
        self.dependencies[task.task_id] = list(depends_on or [])

    def ready(self) -> List[TaskSpec]:
        return [
            task
            for task_id, task in self.tasks.items()
            if all(dep in self.tasks for dep in self.dependencies.get(task_id, []))
        ]
