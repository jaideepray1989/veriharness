from __future__ import annotations

from typing import Protocol, Union

from veriharness.core.types import LeafOutput, LeafRequest

RawLLMOutput = Union[str, dict, LeafOutput]


class LLMClient(Protocol):
    name: str

    def generate(self, request: LeafRequest) -> RawLLMOutput:
        ...
