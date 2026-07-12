from __future__ import annotations

import json
from typing import Any

from veriharness.core.types import Claim, EvidenceRef, HarnessVariant, LeafOutput, LeafRequest


class DummyClient:
    name = "dummy"

    def generate(self, request: LeafRequest) -> LeafOutput:
        task = request.task
        variant = HarnessVariant(request.context_pack.variant)
        if task.family == "context_trace":
            return self._context_trace(request, variant)
        if task.family == "provenance_bias":
            return self._provenance_bias(request, variant)
        if task.family == "swebench_patch":
            return self._swebench_patch(request)
        if task.family == "ds1000":
            return self._ds1000(request)
        if task.family == "humaneval":
            return self._humaneval(request)
        if task.family == "textworld":
            return self._textworld(request)
        if task.family == "mlagentbench":
            return self._mlagentbench(request)
        if task.family in {"boolq", "squad", "multiple_choice", "text_classification"}:
            return self._public_nlp(request)
        return self._mini_workflow(request, variant)

    def _claim(self, text: str, source: str = "task") -> Claim:
        return Claim(
            claim=text,
            evidence_refs=[EvidenceRef(source=source, locator="input", quote=text[:80])],
            confidence=0.8,
        )

    def _context_trace(self, request: LeafRequest, variant: HarnessVariant) -> LeafOutput:
        task = request.task
        meta = task.metadata
        trace_length = int(meta.get("trace_length", 4))
        position = meta.get("constraint_position", "early")
        noise = meta.get("noise_type", "irrelevant")
        overloaded = variant in {HarnessVariant.SELF_ACCEPT, HarnessVariant.H1} and trace_length >= 8
        early_penalty = position == "early" and trace_length >= 8
        conflict_penalty = noise in {"wrong_prior_attempt", "conflicting_doc"}
        wrong = overloaded and (early_penalty or conflict_penalty)
        if variant.uses_state_context:
            wrong = False
        export_format = "csv" if wrong else "jsonl"
        answer = json.dumps(
            {
                "export_format": export_format,
                "fields": task.input_payload.get("required_fields", ["id", "value"]),
            },
            sort_keys=True,
        )
        return LeafOutput(
            task_id=task.task_id,
            answer=answer,
            artifacts=["answer.json"],
            claims=[self._claim(f"export_format is {export_format}")],
            self_assessment={"done_reason": "dummy deterministic answer", "risks": []},
            done=True,
        )

    def _provenance_bias(self, request: LeafRequest, variant: HarnessVariant) -> LeafOutput:
        task = request.task
        label = task.input_payload.get("provenance_label", "tool_note")
        own_bias = label == "own_previous_answer" and variant in {
            HarnessVariant.SELF_ACCEPT,
            HarnessVariant.H1,
            HarnessVariant.H2,
        }
        action = "accept" if own_bias else "reject"
        if variant.uses_external_gates:
            action = "reject"
        done = True
        return LeafOutput(
            task_id=task.task_id,
            answer=json.dumps({"action": action, "claim": task.input_payload.get("wrong_claim")}),
            artifacts=["audit.json"],
            claims=[self._claim(f"Audit action is {action}", source=label)],
            self_assessment={"done_reason": "claim audited", "provenance_label": label},
            done=done,
        )

    def _mini_workflow(self, request: LeafRequest, variant: HarnessVariant) -> LeafOutput:
        task = request.task
        expected = task.hidden_oracle_payload.get("expected_substring", "jsonl")
        wrong = variant in {HarnessVariant.SELF_ACCEPT, HarnessVariant.H1} and "csv" in str(
            task.input_payload.get("raw_trace", [])
        )
        value: Any = "csv" if wrong else expected
        answer = json.dumps({"result": value, "artifact": "workflow_patch.txt"}, sort_keys=True)
        return LeafOutput(
            task_id=task.task_id,
            answer=answer,
            artifacts=["workflow_patch.txt"],
            claims=[self._claim(f"Workflow result preserves {value}")],
            self_assessment={"done_reason": "workflow complete"},
            done=True,
        )

    def _public_nlp(self, request: LeafRequest) -> LeafOutput:
        task = request.task
        payload = task.hidden_oracle_payload
        if task.family == "boolq":
            answer = json.dumps({"answer": bool(payload.get("answer"))}, sort_keys=True)
        elif task.family == "squad":
            answer = json.dumps({"answer": (payload.get("answers") or [""])[0]}, sort_keys=True)
        elif task.family == "multiple_choice":
            answer = json.dumps({"answer": payload.get("answer_label", "")}, sort_keys=True)
        else:
            answer = json.dumps({"label": payload.get("label", "")}, sort_keys=True)
        return LeafOutput(
            task_id=task.task_id,
            answer=answer,
            artifacts=["answer.json"],
            claims=[],
            self_assessment={"done_reason": "dummy public NLP answer"},
            done=True,
        )

    def _swebench_patch(self, request: LeafRequest) -> LeafOutput:
        task = request.task
        patch = str(task.hidden_oracle_payload.get("reference_patch", ""))
        return LeafOutput(
            task_id=task.task_id,
            answer=patch,
            artifacts=["patch.diff"],
            claims=[self._claim("Patch follows the SWE-bench reference patch for smoke validation.")],
            self_assessment={"done_reason": "dummy SWE-bench patch"},
            done=True,
        )

    def _ds1000(self, request: LeafRequest) -> LeafOutput:
        task = request.task
        code = str(task.hidden_oracle_payload.get("reference_code", ""))
        return LeafOutput(
            task_id=task.task_id,
            answer=code,
            artifacts=["solution.py"],
            claims=[self._claim("Solution uses the DS-1000 reference code for smoke validation.")],
            self_assessment={"done_reason": "dummy DS-1000 solution"},
            done=True,
        )

    def _humaneval(self, request: LeafRequest) -> LeafOutput:
        entry_point = str(request.task.input_payload.get("entry_point", "solution"))
        code = f"def {entry_point}(*args, **kwargs):\n    return None\n"
        return LeafOutput(
            task_id=request.task.task_id,
            answer=code,
            artifacts=["solution.py"],
            claims=[],
            self_assessment={"done_reason": "dummy executable placeholder"},
            done=True,
        )

    def _textworld(self, request: LeafRequest) -> LeafOutput:
        return LeafOutput(
            task_id=request.task.task_id,
            answer=json.dumps({"commands": ["look"]}),
            artifacts=["action_plan.json"],
            claims=[],
            self_assessment={"done_reason": "dummy TextWorld probe"},
            done=True,
        )

    def _mlagentbench(self, request: LeafRequest) -> LeafOutput:
        task = request.task
        task_name = str(task.input_payload.get("task_name", ""))
        answer = json.dumps(
            {
                "task_name": task_name,
                "train_command": "python train.py",
                "eval_command": f"python -m MLAgentBench.eval --task {task_name}",
                "expected_artifacts": ["submission.csv", "metrics.json"],
            },
            sort_keys=True,
        )
        return LeafOutput(
            task_id=task.task_id,
            answer=answer,
            artifacts=["research_plan.json"],
            claims=[self._claim(f"MLAgentBench plan targets {task_name}.")],
            self_assessment={"done_reason": "dummy MLAgentBench manifest"},
            done=True,
        )
