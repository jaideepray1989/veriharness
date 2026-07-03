from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from .json_utils import extract_json_object


class LLMProvider:
    name = "base"

    def generate_json(
        self,
        *,
        action: str,
        prompt: str,
        schema: Dict[str, Any],
        artifact_dir: Path,
    ) -> Dict[str, Any]:
        raise NotImplementedError


class CodexProvider(LLMProvider):
    name = "codex"

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        timeout_seconds: int = 900,
        codex_bin: Optional[str] = None,
    ) -> None:
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.codex_bin = codex_bin or os.environ.get("CODEX_BIN") or "codex"

    def generate_json(
        self,
        *,
        action: str,
        prompt: str,
        schema: Dict[str, Any],
        artifact_dir: Path,
    ) -> Dict[str, Any]:
        invocation_id = f"{action}-{uuid.uuid4().hex[:10]}"
        invocation_dir = artifact_dir / "_provider" / invocation_id
        invocation_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = invocation_dir / "prompt.md"
        schema_path = invocation_dir / "schema.json"
        output_path = invocation_dir / "last_message.json"
        stdout_path = invocation_dir / "stdout.txt"
        stderr_path = invocation_dir / "stderr.txt"
        work_dir = invocation_dir / "workspace"
        work_dir.mkdir(parents=True, exist_ok=True)

        prompt_path.write_text(prompt, encoding="utf-8")
        schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")

        cmd = [
            self.codex_bin,
            "-a",
            "never",
            "exec",
            "--ephemeral",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "-C",
            str(work_dir),
            "-",
        ]
        if self.model:
            cmd[4:4] = ["--model", self.model]

        env = os.environ.copy()
        env.setdefault("NO_COLOR", "1")
        try:
            completed = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            raise RuntimeError(f"Codex provider timed out during {action}") from exc

        stdout_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        if completed.returncode != 0:
            raise RuntimeError(
                f"Codex provider failed during {action} with exit code {completed.returncode}. "
                f"See {stderr_path}"
            )
        if output_path.exists():
            raw = output_path.read_text(encoding="utf-8")
        else:
            raw = completed.stdout
        parsed = extract_json_object(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"Codex provider returned non-object JSON for {action}")
        return parsed


class MockProvider(LLMProvider):
    """Deterministic provider for tests and orchestration smoke checks only."""

    name = "mock"

    def generate_json(
        self,
        *,
        action: str,
        prompt: str,
        schema: Dict[str, Any],
        artifact_dir: Path,
    ) -> Dict[str, Any]:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / f"{action}.mock-prompt.md").write_text(prompt, encoding="utf-8")
        required = set(schema.get("required", []))
        if "tasks" in required:
            return {
                "research_plan_id": "mock-plan",
                "synthesis_brief": "Mock bounded task graph for harness smoke testing.",
                "tasks": [
                    {
                        "task_id": "methods",
                        "title": "Map method families",
                        "worker_kind": "method_analyst",
                        "question": "Which method families matter most?",
                        "instructions": "Identify practical options and tradeoffs.",
                        "expected_output": ["claims", "tradeoffs"],
                    },
                    {
                        "task_id": "evaluation",
                        "title": "Map evaluation criteria",
                        "worker_kind": "evaluation_reviewer",
                        "question": "How should results be evaluated?",
                        "instructions": "Identify metrics, baselines, and failure modes.",
                        "expected_output": ["criteria", "risks"],
                    },
                ],
            }
        if "findings" in required:
            task_id = "mock-task"
            if '"task_id": "methods"' in prompt:
                task_id = "methods"
            elif '"task_id": "evaluation"' in prompt:
                task_id = "evaluation"
            return {
                "task_id": task_id,
                "worker_kind": "mock_worker",
                "summary": f"Mock worker summary for {task_id}.",
                "findings": [
                    {
                        "claim": "Use budget-aware comparisons.",
                        "rationale": "Optimization methods change ranking with cost regime.",
                        "evidence_hint": "Common HPO/autotuning practice.",
                        "actionability": "Report wall-clock, evaluations, and regret curves.",
                    }
                ],
                "assumptions": ["Mock provider used for orchestration only."],
                "uncertainties": ["No real research was performed by the mock provider."],
                "next_questions": ["Run with provider=codex for real LLM leaf work."],
                "confidence": 0.1,
            }
        return {
            "plan_id": "mock-plan",
            "executive_summary": "Mock synthesis completed.",
            "answer": "The harness routed principal, worker, and synthesis actions through provider calls.",
            "findings_by_question": [
                {
                    "question": "Mock question",
                    "answer": "Mock answer.",
                    "supporting_worker_tasks": ["methods", "evaluation"],
                }
            ],
            "recommendations": ["Use provider=codex for actual research runs."],
            "conflicts_or_tensions": ["Mock output is not a research result."],
            "open_questions": ["None for the harness smoke test."],
            "confidence": 0.1,
        }


def make_provider(name: str, *, model: Optional[str], timeout_seconds: int) -> LLMProvider:
    normalized = name.strip().lower()
    if normalized == "codex":
        return CodexProvider(model=model, timeout_seconds=timeout_seconds)
    if normalized == "mock":
        return MockProvider()
    raise ValueError(f"unknown provider: {name}")
