from __future__ import annotations

from typing import Protocol

from veriharness.core.types import LeafOutput, TaskSpec


class Benchmark(Protocol):
    name: str

    def generate(self, n_tasks: int, seed: int) -> list[TaskSpec]:
        ...

    def evaluate(self, task: TaskSpec, output: LeafOutput) -> bool:
        ...
