from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

from veriharness.core.types import LeafOutput, LeafRequest
from veriharness.leaves.prompts import render_leaf_prompt


class CoreAIUnavailableError(RuntimeError):
    pass


class CoreAIClient:
    """Local Apple FoundationModels client, exposed as the CoreAI backend."""

    name = "coreai"

    def __init__(
        self,
        *,
        bridge_path: Optional[Path] = None,
        max_tokens: int = 768,
        timeout_seconds: int = 180,
        structured: bool = True,
    ) -> None:
        self.bridge_path = bridge_path or Path(__file__).resolve().parents[1] / "coreai_bridge" / "CoreAILeafBridge.swift"
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.structured = structured

    def generate(self, request: LeafRequest) -> LeafOutput:
        prompt = render_leaf_prompt(request)
        prompt += (
            "\n\nReturn exactly one JSON object matching this shape:\n"
            "{"
            '"task_id": string, "answer": string, "artifacts": [string], '
            '"claims": [{"claim": string, "evidence_refs": [{"source": string}]}], '
            '"self_assessment": object, "done": boolean'
            "}\n"
        )
        payload = {
            "instructions": (
                "You are a bounded VeriHarness worker. "
                "You do not decide final acceptance. Return only valid JSON."
            ),
            "prompt": prompt,
            "maxTokens": self.max_tokens,
        }
        if self.structured:
            payload["taskId"] = request.task.task_id
            payload["taskFamily"] = request.task.family
        response = self._call_bridge(payload)
        content = response["content"]
        return LeafOutput.model_validate(_extract_json(content))

    def availability(self) -> Dict[str, Any]:
        return self._call_bridge({"prompt": "", "availabilityOnly": True}, allow_unavailable=True)

    def _call_bridge(self, payload: Dict[str, Any], allow_unavailable: bool = False) -> Dict[str, Any]:
        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        completed = subprocess.run(
            [str(self._compiled_bridge())],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise CoreAIUnavailableError(
                f"CoreAI bridge failed with exit code {completed.returncode}: {completed.stderr.strip()}"
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise CoreAIUnavailableError(
                f"CoreAI bridge returned non-JSON stdout: {completed.stdout[:500]}"
            ) from exc
        if not response.get("ok") and not allow_unavailable:
            raise CoreAIUnavailableError(response.get("error", "CoreAI unavailable"))
        return response

    def _compiled_bridge(self) -> Path:
        cache_dir = Path(".veriharness_cache")
        cache_dir.mkdir(parents=True, exist_ok=True)
        binary = cache_dir / "coreai_leaf_bridge"
        if binary.exists() and binary.stat().st_mtime >= self.bridge_path.stat().st_mtime:
            return binary
        completed = subprocess.run(
            [
                "swiftc",
                "-parse-as-library",
                str(self.bridge_path),
                "-o",
                str(binary),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise CoreAIUnavailableError(
                f"Failed to compile CoreAI bridge: {completed.stderr.strip()}"
            )
        return binary


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start == -1:
        raise ValueError("CoreAI response did not contain a JSON object")
    stack = []
    in_string = False
    escaped = False
    for index, char in enumerate(stripped[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "}":
            if not stack:
                continue
            stack.pop()
            if not stack:
                value = json.loads(stripped[start : index + 1])
                if not isinstance(value, dict):
                    raise ValueError("CoreAI response JSON was not an object")
                return value
    raise ValueError("CoreAI response did not contain a complete JSON object")
