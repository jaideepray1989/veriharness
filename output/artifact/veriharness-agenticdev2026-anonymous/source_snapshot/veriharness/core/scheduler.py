from __future__ import annotations

from typing import Iterable, Iterator, Tuple

from veriharness.core.types import HarnessVariant, TaskSpec


def schedule_tasks(tasks: Iterable[TaskSpec], variants: Iterable[HarnessVariant]) -> Iterator[Tuple[HarnessVariant, TaskSpec]]:
    for variant in variants:
        for task in tasks:
            yield variant, task
