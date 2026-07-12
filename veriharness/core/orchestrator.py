from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from veriharness.benchmarks.generators import generate_benchmark_tasks
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.context_pack import build_context_pack
from veriharness.core.event_log import EventLog
from veriharness.core.repair_policy import (
    build_diagnostic_retry_feedback,
    build_full_typed_preserve_feedback,
    build_natural_retry_feedback,
    build_location_observed_feedback,
    build_retry_feedback,
    build_same_info_natural_feedback,
    build_targeted_untyped_feedback,
    build_typed_field_feedback,
    build_typed_label_only_feedback,
)
from veriharness.core.run_manager import RunManager
from veriharness.core.scheduler import schedule_tasks
from veriharness.core.state_store import StateStore
from veriharness.core.types import (
    ExperimentConfig,
    ExperimentResult,
    GateResult,
    HarnessVariant,
    LeafOutput,
    LeafRequest,
    TaskSpec,
    canonical_variant_name,
)
from veriharness.experiments.aggregate import write_aggregate
from veriharness.gates.gate_stack import GateStack
from veriharness.leaves.leaf_runner import LeafRunner
from veriharness.llm.base import LLMClient
from veriharness.llm.coreai_client import CoreAIClient
from veriharness.llm.dummy_client import DummyClient
from veriharness.llm.local_client import LocalClient
from veriharness.llm.openai_client import OpenAIClient


def make_client(config: ExperimentConfig) -> LLMClient:
    if config.model.client == "dummy":
        return DummyClient()
    if config.model.client == "coreai":
        return CoreAIClient()
    if config.model.client == "coreai_freeform":
        return CoreAIClient(structured=False)
    if config.model.client == "openai":
        return OpenAIClient(model=config.model.model_name or "gpt-4.1-mini")
    if config.model.client == "local":
        return LocalClient(
            endpoint=config.model.endpoint or "http://localhost:11434/v1/chat/completions",
            model=config.model.model_name or "local",
            max_tokens=config.model.max_output_tokens,
            temperature=config.model.temperature,
            top_p=config.model.top_p,
            seed=config.model.sampling_seed,
            timeout_seconds=config.model.timeout_seconds,
        )
    raise ValueError(f"unknown model client: {config.model.client}")


class Orchestrator:
    def __init__(
        self,
        config: ExperimentConfig,
        *,
        raw_config: Optional[Dict[str, Any]] = None,
        client: Optional[LLMClient] = None,
        run_manager: Optional[RunManager] = None,
        concurrency: int = 1,
    ) -> None:
        self.config = config
        self.raw_config = raw_config or config.model_dump()
        self.client = client or make_client(config)
        self.run_manager = run_manager or RunManager()
        self.concurrency = max(1, int(concurrency))
        self.gates = GateStack(include_oracle=config.evaluation.oracle_guided_acceptance)

    def run(self) -> Path:
        tasks = self._load_tasks()
        run_id, run_dir, store, event_log, state = self.run_manager.create(self.config, self.raw_config)
        event_log.append("experiment_started", payload={"tasks": len(tasks), "variants": [v.value for v in self.config.variants]})
        results_path = run_dir / "results.jsonl"
        schedule = list(schedule_tasks(tasks, self.config.variants))
        if self.concurrency > 1:
            self._run_schedule_parallel(schedule, results_path, store, event_log, state)
        else:
            for variant, task in schedule:
                result = self.run_task_variant(task, variant, store, event_log, state)
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(result.model_dump_json() + "\n")
                state.append_leaderboard_row(result.model_dump())
        aggregate = write_aggregate(run_dir)
        event_log.append("experiment_completed", payload={"aggregate": aggregate})
        return run_dir

    def _run_schedule_parallel(
        self,
        schedule: List[Tuple[HarnessVariant, TaskSpec]],
        results_path: Path,
        store: ArtifactStore,
        event_log: EventLog,
        state: StateStore,
    ) -> None:
        """Run task-variant pairs concurrently.

        Safe because each (variant, task) is independent: no cross-task shared
        state is read/written during execution, the LLM client is stateless per
        call, gates are pure over their inputs, and artifacts are written to
        per-leaf paths. The only shared writers are the results file (guarded
        here), plus StateStore and EventLog (internally locked).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        write_lock = threading.Lock()

        def _work(variant: HarnessVariant, task: TaskSpec):
            return self.run_task_variant(task, variant, store, event_log, state)

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(_work, variant, task) for variant, task in schedule]
            for future in as_completed(futures):
                result = future.result()
                with write_lock:
                    with results_path.open("a", encoding="utf-8") as handle:
                        handle.write(result.model_dump_json() + "\n")
                state.append_leaderboard_row(result.model_dump())

    def resume(self, run_dir: Path) -> Dict[str, Any]:
        run_dir = Path(run_dir)
        if not run_dir.exists():
            raise FileNotFoundError(f"run directory does not exist: {run_dir}")

        tasks = self._load_tasks()
        total_expected = len(tasks) * len(self.config.variants)
        results_path = run_dir / "results.jsonl"
        completed_keys, existing_rows = self._completed_result_keys(results_path)

        run_id = run_dir.name
        store = ArtifactStore(run_dir, run_id)
        event_log = EventLog(run_dir / "events.jsonl", self.config.experiment_id, run_id)
        state = StateStore(run_dir / "state.json")
        remaining = max(0, total_expected - len(completed_keys))
        event_log.append(
            "experiment_resumed",
            payload={
                "tasks": len(tasks),
                "variants": [v.value for v in self.config.variants],
                "existing_rows": existing_rows,
                "completed_pairs": len(completed_keys),
                "remaining": remaining,
            },
        )

        remaining_schedule = [
            (variant, task)
            for variant, task in schedule_tasks(tasks, self.config.variants)
            if self._task_result_key(variant, task) not in completed_keys
        ]
        if self.concurrency > 1:
            self._run_schedule_parallel(remaining_schedule, results_path, store, event_log, state)
            resumed_rows = len(remaining_schedule)
        else:
            resumed_rows = 0
            for variant, task in remaining_schedule:
                result = self.run_task_variant(task, variant, store, event_log, state)
                with results_path.open("a", encoding="utf-8") as handle:
                    handle.write(result.model_dump_json() + "\n")
                state.append_leaderboard_row(result.model_dump())
                completed_keys.add(self._task_result_key(variant, task))
                resumed_rows += 1

        aggregate = write_aggregate(run_dir)
        event_log.append(
            "experiment_completed",
            payload={
                "aggregate": aggregate,
                "resume": True,
                "expected_rows": total_expected,
                "resumed_rows": resumed_rows,
                "completed_pairs": len(completed_keys),
            },
        )
        return {
            "run_dir": str(run_dir),
            "expected_rows": total_expected,
            "existing_rows": existing_rows,
            "completed_pairs": len(completed_keys),
            "resumed_rows": resumed_rows,
            "aggregate": aggregate,
        }

    def _load_tasks(self) -> List[TaskSpec]:
        tasks: List[TaskSpec] = []
        for benchmark in self.config.benchmarks:
            tasks.extend(generate_benchmark_tasks(benchmark))
        return tasks

    def _completed_result_keys(self, results_path: Path) -> tuple[Set[Tuple[str, str, str, str]], int]:
        if not results_path.exists():
            return set(), 0
        completed: Set[Tuple[str, str, str, str]] = set()
        rows = 0
        with results_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON in {results_path} at line {line_number}") from exc
                key = self._row_result_key(row)
                if key:
                    completed.add(key)
                rows += 1
        return completed, rows

    def _task_result_key(self, variant: HarnessVariant, task: TaskSpec) -> Tuple[str, str, str, str]:
        return (
            variant.value,
            str(task.metadata.get("benchmark", task.family)),
            task.task_id,
            str(task.metadata.get("seed", 0)),
        )

    def _row_result_key(self, row: Dict[str, Any]) -> Optional[Tuple[str, str, str, str]]:
        variant = canonical_variant_name(row.get("variant", ""))
        benchmark = str(row.get("benchmark", ""))
        task_id = str(row.get("task_id", ""))
        seed = str(row.get("seed", 0))
        if not variant or not benchmark or not task_id:
            return None
        return (variant, benchmark, task_id, seed)

    def run_task_variant(
        self,
        task: TaskSpec,
        variant: HarnessVariant,
        store: ArtifactStore,
        event_log: EventLog,
        state: StateStore,
    ) -> ExperimentResult:
        start = time.monotonic()
        event_log.append("task_started", task_id=task.task_id, variant=variant.value, payload={"family": task.family})
        state.set_task_status(task.task_id, variant.value, "running")

        if variant.uses_external_gates:
            accepted, output, gate_results, leaf_calls, retries, leaf_dir = self._run_gated(task, variant, store, event_log)
            accepted_by_agent = output.done if output else False
            accepted_by_gate = accepted
            success_gate = self._oracle_passed(gate_results)
            success = accepted and success_gate
        else:
            output, gate_results, leaf_calls, leaf_dir = self._run_self_accept(task, variant, store, event_log)
            accepted_by_agent = output.done
            accepted_by_gate = False
            success = self._oracle_passed(gate_results)
            retries = 0

        output = output or LeafOutput(task_id=task.task_id, answer="", done=False)
        reasons = self._failure_reasons(gate_results)
        premature_stop = bool(accepted_by_agent and not success)
        wrong_claim_accepted = self._wrong_claim_accepted(task, output, success)
        constraint_violation = self._constraint_violation(task, output, success)
        status = "accepted" if success else "rejected"
        state.set_task_status(task.task_id, variant.value, status)
        state.set_open_failures(task.task_id, variant.value, reasons)
        event_log.append(
            "task_accepted" if success else "task_rejected",
            task_id=task.task_id,
            variant=variant.value,
            payload={"failure_reasons": reasons},
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
            tokens_in=self._estimate_tokens(task, variant),
            tokens_out=max(1, len(output.answer.split())),
            num_leaf_calls=leaf_calls,
            num_retries=retries,
            wall_time_sec=time.monotonic() - start,
            failure_reasons=reasons,
            run_path=leaf_dir,
            metadata={
                "call_budget": self.config.budget.max_leaf_calls_per_task,
                "oracle_guided_acceptance": self.config.evaluation.oracle_guided_acceptance,
                "result_role": self.config.evaluation.result_role,
                "temperature": self.config.model.temperature,
                "top_p": self.config.model.top_p,
                "sampling_seed": self.config.model.sampling_seed,
                "max_output_tokens": self.config.model.max_output_tokens,
                "repair_policy": self._repair_policy_name(variant),
                "repair_target_policy": self._repair_target_policy_name(variant),
                "baseline_family": self._baseline_family(variant),
                "candidate_retention": variant.uses_candidate_retention,
                "candidate_count": self._candidate_count(variant),
            },
        )

    def _run_self_accept(
        self,
        task: TaskSpec,
        variant: HarnessVariant,
        store: ArtifactStore,
        event_log: EventLog,
    ) -> tuple[LeafOutput, List[GateResult], int, str]:
        context = build_context_pack(task, variant, self.config.budget)
        leaf_dir = f"{self._leaf_base_dir(task, variant)}/attempt_0/candidate_0"
        event_log.append("context_pack_created", task_id=task.task_id, variant=variant.value, payload={"leaf_dir": leaf_dir})
        output = self._run_leaf(task, variant, context, store, event_log, leaf_dir, attempt=0, candidate_id="candidate-0")
        oracle_result = evaluate_oracle(task, output)
        oracle_result.metadata["used_for_acceptance"] = False
        oracle_result.metadata["evaluation"] = "posthoc_self_accept"
        store.write_json(f"{leaf_dir}/gate_results.json", [oracle_result.model_dump()])
        self._write_leaf_event_copy(store, leaf_dir, event_log)
        return output, [oracle_result], 1, leaf_dir

    def _run_gated(
        self,
        task: TaskSpec,
        variant: HarnessVariant,
        store: ArtifactStore,
        event_log: EventLog,
    ) -> tuple[bool, Optional[LeafOutput], List[GateResult], int, int, str]:
        retry_feedback: List[str] = []
        leaf_calls = 0
        last_output: Optional[LeafOutput] = None
        last_results: List[GateResult] = []
        last_leaf_dir = ""
        max_retries = self.config.budget.max_retries
        call_budget = max(1, self.config.budget.max_leaf_calls_per_task)
        last_attempt = 0
        for attempt in range(max_retries + 1):
            if leaf_calls >= call_budget:
                break
            last_attempt = attempt
            context = build_context_pack(task, variant, self.config.budget, retry_feedback=retry_feedback)
            candidates = self._candidate_count(variant)
            candidates = min(candidates, call_budget - leaf_calls)
            candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]] = []
            for candidate_index in range(candidates):
                candidate_id = f"candidate-{candidate_index}"
                leaf_dir = f"{self._leaf_base_dir(task, variant)}/attempt_{attempt}/{candidate_id}"
                output = self._run_leaf(task, variant, context, store, event_log, leaf_dir, attempt, candidate_id)
                leaf_calls += 1
                passed, gate_results = self._run_gates(task, output, store, event_log, leaf_dir, variant)
                candidate_results.append((passed, output, gate_results, leaf_dir))
                last_output = output
                last_results = gate_results
                last_leaf_dir = leaf_dir
                if passed:
                    return True, output, gate_results, leaf_calls, attempt, leaf_dir
            retry_feedback = self._repair_feedback(task, context, candidate_results, variant)
            if attempt < max_retries and leaf_calls < call_budget:
                event_log.append(
                    "task_retried",
                    task_id=task.task_id,
                    variant=variant.value,
                    payload={"failures": retry_feedback},
                )
        return False, last_output, last_results, leaf_calls, last_attempt, last_leaf_dir

    def _leaf_base_dir(self, task: TaskSpec, variant: HarnessVariant) -> str:
        benchmark = self._safe_path_part(str(task.metadata.get("benchmark", task.family)))
        seed = self._safe_path_part(str(task.metadata.get("seed", 0)))
        task_id = self._safe_path_part(task.task_id)
        return f"artifacts/leaves/{variant.value}/{benchmark}/seed_{seed}/{task_id}"

    def _safe_path_part(self, value: str) -> str:
        return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)[:160] or "item"

    def _candidate_count(self, variant: HarnessVariant) -> int:
        if variant.uses_best_of_n_gated:
            return max(1, self.config.budget.max_leaf_calls_per_task)
        if variant.uses_candidate_retention:
            return max(1, self.config.budget.veriharness_k)
        return 1

    def _run_leaf(
        self,
        task: TaskSpec,
        variant: HarnessVariant,
        context: Any,
        store: ArtifactStore,
        event_log: EventLog,
        leaf_dir: str,
        attempt: int,
        candidate_id: str,
    ) -> LeafOutput:
        request = LeafRequest(
            context_pack=context,
            task=task,
            attempt=attempt,
            candidate_id=candidate_id,
            retry_feedback=list(context.current_state.get("retry_feedback", [])),
        )
        runner = LeafRunner(self.client, store)
        event_log.append("leaf_started", task_id=task.task_id, variant=variant.value, payload={"leaf_dir": leaf_dir})
        output = runner.run(request, leaf_dir)
        event_log.append("leaf_completed", task_id=task.task_id, variant=variant.value, payload={"done": output.done})
        return output

    def _run_gates(
        self,
        task: TaskSpec,
        output: LeafOutput,
        store: ArtifactStore,
        event_log: EventLog,
        leaf_dir: str,
        variant: HarnessVariant,
    ) -> tuple[bool, List[GateResult]]:
        event_log.append("gate_started", task_id=task.task_id, variant=variant.value, payload={"leaf_dir": leaf_dir})
        passed, results = self.gates.evaluate(task, output, store, leaf_dir)
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
        self._write_leaf_event_copy(store, leaf_dir, event_log)
        event_log.append(
            "gate_completed",
            task_id=task.task_id,
            variant=variant.value,
            payload={"passed": passed, "oracle_guided": self.config.evaluation.oracle_guided_acceptance},
        )
        return passed, results

    def _write_leaf_event_copy(self, store: ArtifactStore, leaf_dir: str, event_log: EventLog) -> None:
        rows = list(event_log.read())
        relevant = [row for row in rows if row.get("payload", {}).get("leaf_dir") == leaf_dir]
        if not relevant:
            relevant = rows[-5:]
        store.write_text(f"{leaf_dir}/event_log.jsonl", "".join(json.dumps(row, sort_keys=True) + "\n" for row in relevant))

    def _oracle_passed(self, results: List[GateResult]) -> bool:
        oracle = [result for result in results if result.gate_name == "oracle"]
        return bool(oracle and oracle[-1].passed)

    def _failure_reasons(self, results: List[GateResult]) -> List[str]:
        reasons: List[str] = []
        for result in results:
            for failure in result.failures:
                reasons.append(failure.code)
        return reasons

    def _repair_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
        variant: HarnessVariant,
    ) -> List[str]:
        if variant.uses_generic_retry:
            return self._generic_retry_feedback(candidate_results)
        if variant.uses_diagnostic_retry:
            return self._diagnostic_retry_feedback(task, context, candidate_results)
        if variant.uses_natural_retry:
            return self._natural_retry_feedback(task, context, candidate_results)
        if variant.uses_same_info_natural_repair:
            return self._same_info_natural_feedback(task, context, candidate_results)
        if variant.uses_location_observed_repair:
            return self._location_observed_feedback(task, context, candidate_results)
        if variant.uses_langgraph_validator_retry:
            return self._langgraph_validator_retry_feedback(task, context, candidate_results)
        if variant.uses_targeted_untyped_repair:
            return self._targeted_untyped_feedback(task, context, candidate_results)
        if variant.uses_typed_label_only_repair:
            return self._typed_label_only_feedback(task, context, candidate_results)
        if variant.uses_typed_field_repair:
            return self._typed_field_feedback(task, context, candidate_results)
        if variant.uses_full_typed_preserve_repair:
            return self._full_typed_preserve_feedback(task, context, candidate_results)
        if not variant.uses_typed_repair:
            return []
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_retry_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _repair_visible_results(self, results: List[GateResult]) -> List[GateResult]:
        if self.config.evaluation.oracle_guided_acceptance:
            return results
        return [
            result
            for result in results
            if not (
                result.gate_name == "oracle"
                and result.metadata.get("evaluation") == "posthoc_oracle_blind"
            )
        ]

    def _generic_retry_feedback(self, candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]]) -> List[str]:
        visible_failures = [
            failure
            for _passed, _output, gate_results, _leaf_dir in candidate_results
            for result in self._repair_visible_results(gate_results)
            for failure in result.failures
        ]
        if not visible_failures:
            return []
        return [
            "Previous attempt failed acceptance checks. Try again with a complete valid answer.",
            "Keep the requested output schema and artifacts, and do not add prose outside the structured output.",
        ]

    def _natural_retry_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_natural_retry_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _diagnostic_retry_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_diagnostic_retry_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _same_info_natural_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_same_info_natural_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _location_observed_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_location_observed_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _langgraph_validator_retry_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback = [
            "Validator-retry graph state: generation node produced a candidate; validation node rejected it; retry node must revise the same task output.",
        ]
        for item in self._natural_retry_feedback(task, context, candidate_results):
            if item not in feedback:
                feedback.append(item)
        return feedback

    def _targeted_untyped_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_targeted_untyped_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _typed_label_only_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_typed_label_only_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _typed_field_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_typed_field_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _full_typed_preserve_feedback(
        self,
        task: TaskSpec,
        context: Any,
        candidate_results: List[tuple[bool, LeafOutput, List[GateResult], str]],
    ) -> List[str]:
        feedback: List[str] = []
        for _passed, output, gate_results, _leaf_dir in candidate_results:
            visible_results = self._repair_visible_results(gate_results)
            for item in build_full_typed_preserve_feedback(task, context, output, visible_results):
                if item not in feedback:
                    feedback.append(item)
        return feedback

    def _repair_policy_name(self, variant: HarnessVariant) -> str:
        if variant.uses_generic_retry:
            return "generic"
        if variant.uses_diagnostic_retry:
            return "generic_raw_validation_message"
        if variant.uses_natural_retry:
            return "natural_language_gate_error"
        if variant.uses_same_info_natural_repair:
            return "same_information_natural_language"
        if variant.uses_location_observed_repair:
            return "typed_failure_location_observed_no_expected"
        if variant.uses_best_of_n_gated:
            return "none_best_of_n"
        if variant.uses_langgraph_validator_retry:
            return "langgraph_validator_retry"
        if variant.uses_targeted_untyped_repair:
            return "targeted_untyped"
        if variant.uses_typed_label_only_repair:
            return "typed_failure_label_only"
        if variant.uses_typed_field_repair:
            return "typed_failure_location_expected_observed"
        if variant.uses_full_typed_preserve_repair:
            return "full_typed_repair_preserve_set"
        if variant.uses_typed_repair:
            return "typed_failure_payload"
        return "none"

    def _repair_target_policy_name(self, variant: HarnessVariant) -> str:
        if variant.uses_targeted_untyped_repair:
            return "priority_single_locus"
        if variant.uses_typed_label_only_repair:
            return "all_visible_failure_labels"
        if variant.uses_same_info_natural_repair:
            return "all_visible_failure_fields_as_prose"
        if variant.uses_location_observed_repair:
            return "all_visible_failure_locations_without_expected"
        if variant.uses_typed_field_repair:
            return "all_visible_failure_fields"
        if variant.uses_full_typed_preserve_repair:
            return "all_visible_failure_fields_plus_preserve_set"
        if variant.uses_typed_repair:
            return "all_visible_failures_in_gate_order"
        if variant.uses_best_of_n_gated:
            return "none_best_of_n"
        if variant.uses_langgraph_validator_retry:
            return "generate_validate_retry_graph"
        if variant.uses_generic_retry or variant.uses_diagnostic_retry or variant.uses_natural_retry:
            return "all_visible_failures_unprioritized"
        return "none"

    def _baseline_family(self, variant: HarnessVariant) -> str:
        if variant.uses_best_of_n_gated:
            return "best_of_n_gated"
        if variant.uses_langgraph_validator_retry:
            return "validator_retry_graph"
        if variant.uses_diagnostic_retry:
            return "raw_diagnostics_retry"
        if variant.uses_natural_retry:
            return "reflexion_style_verbal_retry"
        if variant.uses_same_info_natural_repair:
            return "same_information_natural_language"
        if variant == HarnessVariant.TYPED_REPAIR_RETAIN:
            return "veriharness"
        if variant == HarnessVariant.GATED_RESAMPLE:
            return "external_gates"
        if variant == HarnessVariant.SELF_ACCEPT:
            return "self_accept"
        return "internal_ablation"

    def _wrong_claim_accepted(self, task: TaskSpec, output: LeafOutput, success: bool) -> bool:
        if task.family != "provenance_bias":
            return False
        try:
            data = json.loads(output.answer)
        except Exception:
            return False
        return str(data.get("action", "")).lower() == "accept" and not success

    def _constraint_violation(self, task: TaskSpec, output: LeafOutput, success: bool) -> bool:
        if task.family == "context_trace":
            return not success
        return any(code in self._failure_codes_from_output(task, output) for code in ["distractor_adopted", "constraint_forgotten"])

    def _failure_codes_from_output(self, task: TaskSpec, output: LeafOutput) -> List[str]:
        return [failure.code for failure in evaluate_oracle(task, output).failures]

    def _estimate_tokens(self, task: TaskSpec, variant: HarnessVariant) -> int:
        pack = build_context_pack(task, variant, self.config.budget)
        return max(1, len(pack.model_dump_json().split()))
