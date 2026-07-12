from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from veriharness.core.types import LeafRequest
from veriharness.llm.base import RawLLMOutput


class ScriptedClient:
    name = "scripted"

    def __init__(self, outputs: Dict[str, RawLLMOutput | List[RawLLMOutput]]) -> None:
        self.outputs = outputs
        self.calls = defaultdict(int)

    def generate(self, request: LeafRequest) -> RawLLMOutput:
        key = request.task.task_id
        value = self.outputs.get(key, self.outputs.get("*"))
        if isinstance(value, list):
            index = min(self.calls[key], len(value) - 1)
            self.calls[key] += 1
            return value[index]
        if value is None:
            raise KeyError(f"no scripted output for task {key}")
        self.calls[key] += 1
        return value
