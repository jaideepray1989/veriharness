from __future__ import annotations

import os

from veriharness.core.types import LeafOutput, LeafRequest
from veriharness.leaves.prompts import render_leaf_prompt


class OpenAIClient:
    name = "openai"

    def __init__(self, model: str = "gpt-4.1-mini") -> None:
        self.model = model
        self.enabled = bool(os.environ.get("OPENAI_API_KEY"))

    def generate(self, request: LeafRequest) -> LeafOutput:
        if not self.enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("openai package is not installed") from exc

        client = OpenAI()
        response = client.responses.create(
            model=self.model,
            instructions="You are a bounded VeriHarness worker. Return only valid LeafOutput JSON.",
            input=render_leaf_prompt(request),
        )
        text = response.output_text
        return LeafOutput.model_validate_json(text)
