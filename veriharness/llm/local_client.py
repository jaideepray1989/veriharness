from __future__ import annotations

import json
import urllib.request

from veriharness.core.types import LeafOutput, LeafRequest
from veriharness.leaves.prompts import render_leaf_prompt


class LocalClient:
    name = "local"

    def __init__(
        self,
        endpoint: str = "http://localhost:11434/v1/chat/completions",
        model: str = "local",
        max_tokens: int = 768,
        temperature: float = 0.0,
        top_p: float | None = None,
        timeout_seconds: int = 120,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.timeout_seconds = timeout_seconds

    def generate(self, request: LeafRequest) -> LeafOutput:
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
            "messages": [
                {"role": "system", "content": "Return only LeafOutput JSON."},
                {"role": "user", "content": render_leaf_prompt(request)},
            ],
        }
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:  # nosec - user configured local endpoint
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return LeafOutput.model_validate_json(content)
