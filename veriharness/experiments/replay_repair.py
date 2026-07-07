from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from veriharness.benchmarks.generators import generate_benchmark_tasks
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.context_pack import build_context_pack
from veriharness.core.event_log import EventLog
from veriharness.core.orchestrator import Orchestrator
from veriharness.core.run_manager import RunManager
from veriharness.core.state_store import StateStore
from veriharness.core.types import (
    Claim,
    EvidenceRef,
    ExperimentConfig,
    ExperimentResult,
    GateResult,
    HarnessVariant,
    LeafOutput,
    TaskSpec,
)
from veriharness.experiments.aggregate import write_aggregate
from veriharness.llm.base import LLMClient


class ReplayRepairRunner:
    """Run a causal repair-message benchmark from frozen failed attempts.

    Each task gets one deterministic failed first attempt. Every repair policy
    then receives the same failed output and gate result, and gets exactly one
    leaf call to repair it. This isolates repair-message content from first-pass
    generation drift.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        *,
        raw_config: Optional[Dict[str, Any]] = None,
        client: Optional[LLMClient] = None,
        run_manager: Optional[RunManager] = None,
    ) -> None:
        self.config = config
        self.raw_config = raw_config or config.model_dump()
        self.orchestrator = Orchestrator(config, raw_config=self.raw_config, client=client, run_manager=run_manager)
        self.run_manager = self.orchestrator.run_manager

    def run(self) -> Path:
        tasks = self._load_tasks()
        run_id, run_dir, store, event_log, state = self.run_manager.create(self.config, self.raw_config)
        event_log.append(
            "experiment_started",
            payload={
                "tasks": len(tasks),
                "variants": [variant.value for variant in self.config.variants],
                "mode": "replay_repair",
            },
        )
        results_path = run_dir / "results.jsonl"
        frozen_path = run_dir / "frozen_failures.jsonl"

        for task in tasks:
            frozen_output, frozen_results, frozen_dir = self._create_frozen_failure(task, store, event_log)
            with frozen_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "task_id": task.task_id,
                            "benchmark": task.metadata.get("benchmark", task.family),
                            "seed": task.metadata.get("seed", 0),
                            "frozen_path": frozen_dir,
                            "failure_reasons": self.orchestrator._failure_reasons(frozen_results),
                            "answer": frozen_output.answer,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
            for variant in self.config.variants:
                result = self._run_repair_variant(
                    task=task,
                    variant=variant,
                    frozen_output=frozen_output,
                    frozen_results=frozen_results,
                    frozen_dir=frozen_dir,
                    store=store,
                    event_log=event_log,
                    state=state,
                )
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(result.model_dump_json() + "\n")
                state.append_leaderboard_row(result.model_dump())

        aggregate = write_aggregate(run_dir)
        event_log.append("experiment_completed", payload={"aggregate": aggregate, "mode": "replay_repair"})
        return run_dir

    def _load_tasks(self) -> List[TaskSpec]:
        tasks: List[TaskSpec] = []
        for benchmark in self.config.benchmarks:
            tasks.extend(generate_benchmark_tasks(benchmark))
        return tasks

    def _create_frozen_failure(
        self,
        task: TaskSpec,
        store: ArtifactStore,
        event_log: EventLog,
    ) -> tuple[LeafOutput, List[GateResult], str]:
        leaf_dir = f"artifacts/replay_frozen/{self._task_path(task)}/attempt_0/candidate-0"
        output = frozen_failed_output(task)
        store.write_json(f"{leaf_dir}/leaf_output.json", output.model_dump())
        for artifact in output.artifacts:
            store.write_text(f"{leaf_dir}/{Path(artifact).name}", output.answer)
        passed, results = self._evaluate(task, output, store, event_log, leaf_dir)
        if passed:
            raise ValueError(f"frozen replay failure unexpectedly passed gates for {task.task_id}")
        return output, results, leaf_dir

    def _run_repair_variant(
        self,
        *,
        task: TaskSpec,
        variant: HarnessVariant,
        frozen_output: LeafOutput,
        frozen_results: List[GateResult],
        frozen_dir: str,
        store: ArtifactStore,
        event_log: EventLog,
        state: StateStore,
    ) -> ExperimentResult:
        start = time.monotonic()
        event_log.append(
            "task_started",
            task_id=task.task_id,
            variant=variant.value,
            payload={"family": task.family, "mode": "replay_repair", "frozen_dir": frozen_dir},
        )
        state.set_task_status(task.task_id, variant.value, "running")

        base_context = build_context_pack(task, variant, self.config.budget)
        retry_feedback = self.orchestrator._repair_feedback(
            task,
            base_context,
            [(False, frozen_output, frozen_results, frozen_dir)],
            variant,
        )
        context = build_context_pack(task, variant, self.config.budget, retry_feedback=retry_feedback)
        leaf_dir = f"{self.orchestrator._leaf_base_dir(task, variant)}/replay_attempt_1/candidate-0"
        output = self.orchestrator._run_leaf(
            task,
            variant,
            context,
            store,
            event_log,
            leaf_dir,
            attempt=1,
            candidate_id="candidate-0",
        )
        accepted_by_gate, gate_results = self.orchestrator._run_gates(task, output, store, event_log, leaf_dir, variant)
        success = accepted_by_gate and self.orchestrator._oracle_passed(gate_results)
        accepted_by_agent = bool(output.done)
        reasons = self.orchestrator._failure_reasons(gate_results)
        premature_stop = bool(accepted_by_agent and not success)
        wrong_claim_accepted = self.orchestrator._wrong_claim_accepted(task, output, success)
        constraint_violation = self.orchestrator._constraint_violation(task, output, success)
        state.set_task_status(task.task_id, variant.value, "accepted" if success else "rejected")
        state.set_open_failures(task.task_id, variant.value, reasons)
        event_log.append(
            "task_accepted" if success else "task_rejected",
            task_id=task.task_id,
            variant=variant.value,
            payload={"failure_reasons": reasons, "mode": "replay_repair"},
        )
        return ExperimentResult(
            experiment_id=self.config.experiment_id,
            task_id=task.task_id,
            benchmark=task.metadata.get("benchmark", task.family),
            variant=variant.value,
            model_client=self.config.model.client,
            model_name=self.config.model.model_name,
            model_provider=self.config.model.provider,
            model_parameter_count=self.config.model.parameter_count,
            model_active_parameter_count=self.config.model.active_parameter_count,
            model_parameter_count_label=self.config.model.parameter_count_label,
            seed=int(task.metadata.get("seed", 0)),
            trace_length=task.metadata.get("trace_length"),
            constraint_position=task.metadata.get("constraint_position"),
            noise_type=task.metadata.get("noise_type"),
            provenance_label=task.metadata.get("provenance_label"),
            success=success,
            accepted_by_agent=accepted_by_agent,
            accepted_by_gate=accepted_by_gate,
            premature_stop=premature_stop,
            wrong_claim_accepted=wrong_claim_accepted,
            constraint_violation=constraint_violation,
            tokens_in=max(1, len(context.model_dump_json().split())),
            tokens_out=max(1, len(output.answer.split())),
            num_leaf_calls=1,
            num_retries=1,
            wall_time_sec=time.monotonic() - start,
            failure_reasons=reasons,
            run_path=leaf_dir,
            metadata={
                "mode": "replay_repair",
                "frozen_failure_path": frozen_dir,
                "frozen_failure_reasons": self.orchestrator._failure_reasons(frozen_results),
                "call_budget": 1,
                "oracle_guided_acceptance": self.config.evaluation.oracle_guided_acceptance,
                "result_role": self.config.evaluation.result_role,
                "temperature": self.config.model.temperature,
                "top_p": self.config.model.top_p,
                "max_output_tokens": self.config.model.max_output_tokens,
                "repair_policy": self.orchestrator._repair_policy_name(variant),
                "repair_target_policy": self.orchestrator._repair_target_policy_name(variant),
                "candidate_retention": False,
                "candidate_count": 1,
            },
        )

    def _evaluate(
        self,
        task: TaskSpec,
        output: LeafOutput,
        store: ArtifactStore,
        event_log: EventLog,
        leaf_dir: str,
    ) -> tuple[bool, List[GateResult]]:
        event_log.append("gate_started", task_id=task.task_id, variant="replay-frozen", payload={"leaf_dir": leaf_dir})
        passed, results = self.orchestrator.gates.evaluate(task, output, store, leaf_dir)
        if not self.config.evaluation.oracle_guided_acceptance:
            oracle_result = evaluate_oracle(task, output)
            oracle_result.metadata["used_for_acceptance"] = False
            oracle_result.metadata["evaluation"] = "posthoc_oracle_blind"
            results = results + [oracle_result]
        else:
            for result in results:
                if result.gate_name == "oracle":
                    result.metadata["used_for_acceptance"] = True
                    result.metadata["evaluation"] = "online_oracle_guided"
        store.write_json(f"{leaf_dir}/gate_results.json", [result.model_dump() for result in results])
        event_log.append(
            "gate_completed",
            task_id=task.task_id,
            variant="replay-frozen",
            payload={"passed": passed, "leaf_dir": leaf_dir, "mode": "replay_repair"},
        )
        return passed, results

    def _task_path(self, task: TaskSpec) -> str:
        benchmark = self.orchestrator._safe_path_part(str(task.metadata.get("benchmark", task.family)))
        seed = self.orchestrator._safe_path_part(str(task.metadata.get("seed", 0)))
        task_id = self.orchestrator._safe_path_part(task.task_id)
        return f"{benchmark}/seed_{seed}/{task_id}"


def frozen_failed_output(task: TaskSpec) -> LeafOutput:
    if task.family == "boolq":
        wrong = not bool(task.hidden_oracle_payload.get("answer"))
        answer = json.dumps({"answer": wrong}, sort_keys=True)
        return _leaf(task, answer, ["answer.json"], claim=f"Frozen wrong BoolQ answer: {wrong}", done=True)
    if task.family == "multiple_choice":
        expected = str(task.hidden_oracle_payload.get("answer_label", ""))
        labels = [
            str(choice.get("label", ""))
            for choice in task.input_payload.get("choices", [])
            if isinstance(choice, dict)
        ]
        wrong = next((label for label in labels if label and label != expected), labels[0] if labels else "A")
        answer = json.dumps({"answer": wrong}, sort_keys=True)
        return _leaf(task, answer, ["answer.json"], claim=f"Frozen wrong multiple-choice label: {wrong}", done=True)
    if task.family == "mini_workflow":
        answer = json.dumps({"artifact": "workflow_patch.txt", "result": "csv"}, sort_keys=True)
        return _leaf(task, answer, ["workflow_patch.txt"], claim="Frozen workflow result uses rejected csv marker.", done=True)
    answer = json.dumps({"answer": "__frozen_wrong__"}, sort_keys=True)
    return _leaf(task, answer, ["answer.json"], claim="Frozen fallback wrong answer.", done=True)


def _leaf(task: TaskSpec, answer: str, artifacts: List[str], *, claim: str, done: bool) -> LeafOutput:
    return LeafOutput(
        task_id=task.task_id,
        answer=answer,
        artifacts=artifacts,
        claims=[
            Claim(
                claim=claim,
                evidence_refs=[EvidenceRef(source="replay_fixture", locator=task.task_id, quote=claim[:80])],
                confidence=0.1,
            )
        ],
        self_assessment={"replay_fixture": True, "done_reason": "controlled frozen failure"},
        done=done,
    )
