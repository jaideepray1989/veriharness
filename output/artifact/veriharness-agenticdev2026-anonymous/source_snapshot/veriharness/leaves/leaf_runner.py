from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.context_pack import context_pack_to_markdown
from veriharness.core.types import LeafOutput, LeafRequest
from veriharness.leaves.prompts import render_leaf_prompt
from veriharness.llm.base import LLMClient, RawLLMOutput


class LeafRunner:
    def __init__(self, client: LLMClient, store: ArtifactStore) -> None:
        self.client = client
        self.store = store

    def run(self, request: LeafRequest, leaf_dir: str) -> LeafOutput:
        prompt = render_leaf_prompt(request)
        self.store.write_text(f"{leaf_dir}/context_pack.md", context_pack_to_markdown(request.context_pack))
        self.store.write_text(f"{leaf_dir}/transcript.txt", prompt)
        try:
            raw = self.client.generate(request)
            if isinstance(raw, LeafOutput):
                raw_trace = raw.model_dump_json()
            elif isinstance(raw, str):
                raw_trace = raw
            else:
                raw_trace = json.dumps(raw, indent=2, sort_keys=True, default=str)
            self.store.write_text(f"{leaf_dir}/raw_response.txt", raw_trace)
            output = self._parse(raw, request)
        except Exception as exc:
            self.store.write_text(f"{leaf_dir}/raw_response.txt", f"client_error: {exc}\n")
            output = LeafOutput(
                task_id=request.task.task_id,
                answer="",
                artifacts=[],
                claims=[],
                self_assessment={
                    "client_error": str(exc),
                    "client": getattr(self.client, "name", self.client.__class__.__name__),
                },
                done=False,
            )
        self.store.write_json(f"{leaf_dir}/leaf_output.json", output.model_dump())
        self.store.write_json(
            f"{leaf_dir}/metadata.json",
            {
                "client": getattr(self.client, "name", self.client.__class__.__name__),
                "attempt": request.attempt,
                "candidate_id": request.candidate_id,
            },
        )
        for artifact in output.artifacts:
            safe_artifact = Path(artifact).name
            if safe_artifact:
                self.store.write_text(f"{leaf_dir}/{safe_artifact}", output.answer)
        return output

    def _parse(self, raw: RawLLMOutput, request: LeafRequest) -> LeafOutput:
        try:
            if isinstance(raw, LeafOutput):
                return raw
            if isinstance(raw, str):
                data: Any = json.loads(raw)
            else:
                data = raw
            if isinstance(data, dict) and "answer" in data and not isinstance(data["answer"], str):
                data = dict(data)
                data["answer"] = json.dumps(data["answer"], sort_keys=True)
            return LeafOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            return LeafOutput(
                task_id=request.task.task_id,
                answer="",
                artifacts=[],
                claims=[],
                self_assessment={"parse_error": str(exc), "raw_type": type(raw).__name__},
                done=False,
            )
