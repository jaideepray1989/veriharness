from pathlib import Path

import json

from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.benchmarks.reading_comprehension import generate_boolq_tasks
from veriharness.core.orchestrator import Orchestrator
from veriharness.core.run_manager import RunManager
from veriharness.core.types import BenchmarkConfig, BudgetConfig, ExperimentConfig, HarnessVariant
from veriharness.experiments.aggregate import aggregate_rows, read_results
from veriharness.experiments.plots import write_plots
from veriharness.experiments.workshop_report import compile_workshop_bundle
from veriharness.llm.dummy_client import DummyClient
from veriharness.llm.scripted_client import ScriptedClient


def test_smoke_experiment_produces_results(tmp_path):
    config = ExperimentConfig(
        experiment_id="smoke-test",
        benchmarks=[
            BenchmarkConfig(name="context_trace", n_tasks=4, trace_lengths=[4, 8], seeds=[1]),
            BenchmarkConfig(name="provenance_bias", n_tasks=4, seeds=[1]),
        ],
        model={
            "client": "dummy",
            "provider": "test",
            "model_name": "mock-70b",
            "parameter_count": 70_000_000_000,
            "parameter_count_label": "70B",
        },
        variants=[HarnessVariant.H0, HarnessVariant.H3, HarnessVariant.H4],
        budget=BudgetConfig(max_retries=1, veriharness_k=2, max_leaf_calls_per_task=4),
    )
    run_dir = Orchestrator(config, client=DummyClient(), run_manager=RunManager(tmp_path)).run()
    rows = read_results(run_dir)
    assert len(rows) == 24
    assert (run_dir / "results.jsonl").exists()
    assert (run_dir / "leaderboard.csv").exists()
    assert (run_dir / "aggregate.json").exists()
    assert rows[0]["model_name"] == "mock-70b"
    assert rows[0]["model_parameter_count"] == 70_000_000_000
    assert rows[0]["model_parameter_count_label"] == "70B"
    assert any(row["premature_stop"] for row in rows if row["variant"] == "H0")


def test_resume_skips_completed_rows_and_finishes_run(tmp_path):
    config = ExperimentConfig(
        experiment_id="resume-test",
        benchmarks=[BenchmarkConfig(name="context_trace", n_tasks=2, trace_lengths=[4], seeds=[1])],
        variants=[HarnessVariant.H0, HarnessVariant.H3],
        budget=BudgetConfig(max_retries=0),
    )
    orch = Orchestrator(config, client=DummyClient(), run_manager=RunManager(tmp_path))
    run_dir = orch.run()
    rows = read_results(run_dir)
    kept = rows[:2]
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in kept:
            handle.write(json.dumps(row) + "\n")
    (run_dir / "aggregate.json").unlink()

    summary = Orchestrator(config, client=DummyClient()).resume(run_dir)
    resumed_rows = read_results(run_dir)

    assert summary["expected_rows"] == 4
    assert summary["existing_rows"] == 2
    assert summary["resumed_rows"] == 2
    assert len(resumed_rows) == 4
    assert len({(row["variant"], row["task_id"]) for row in resumed_rows}) == 4
    assert (run_dir / "aggregate.json").exists()


def test_resume_distinguishes_reused_task_ids_across_seeds(tmp_path):
    config = ExperimentConfig(
        experiment_id="resume-seed-key-test",
        benchmarks=[BenchmarkConfig(name="boolq", n_tasks=2, seeds=[1, 2])],
        variants=[HarnessVariant.H0, HarnessVariant.H3],
        budget=BudgetConfig(max_retries=0),
    )
    orch = Orchestrator(config, client=DummyClient(), run_manager=RunManager(tmp_path))
    run_dir = orch.run()
    rows = read_results(run_dir)
    kept = [row for row in rows if row["variant"] == "H0"]
    assert len(kept) == 4
    assert len({row["task_id"] for row in kept}) < len(kept)
    assert len({row["seed"] for row in kept}) == 2
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in kept:
            handle.write(json.dumps(row) + "\n")
    (run_dir / "aggregate.json").unlink()

    summary = Orchestrator(config, client=DummyClient()).resume(run_dir)
    resumed_rows = read_results(run_dir)

    assert summary["expected_rows"] == 8
    assert summary["existing_rows"] == 4
    assert summary["resumed_rows"] == 4
    assert len(resumed_rows) == 8
    assert len({(row["variant"], row["benchmark"], row["task_id"], row["seed"]) for row in resumed_rows}) == 8


def test_h3_rejects_invalid_output_even_if_done(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    config = ExperimentConfig(
        experiment_id="invalid-test",
        benchmarks=[],
        variants=[HarnessVariant.H3],
        budget=BudgetConfig(max_retries=0),
    )
    client = ScriptedClient({
        task.task_id: {
            "task_id": task.task_id,
            "answer": '{"export_format": "csv", "fields": ["id", "value"]}',
            "artifacts": ["answer.json"],
            "claims": [],
            "self_assessment": {},
            "done": True,
        }
    })
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    run_id, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.H3, store, event_log, state)
    assert result.accepted_by_agent
    assert not result.accepted_by_gate
    assert not result.success


def test_h4_selects_passing_veriharness_candidate(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    config = ExperimentConfig(
        experiment_id="veriharness-test",
        benchmarks=[],
        variants=[HarnessVariant.H4],
        budget=BudgetConfig(max_retries=0, veriharness_k=2),
    )
    bad = {
        "task_id": task.task_id,
        "answer": '{"export_format": "csv", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "bad", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    good = {
        "task_id": task.task_id,
        "answer": '{"export_format": "jsonl", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "good", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    client = ScriptedClient({task.task_id: [bad, good]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, _, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.H4, store, event_log, state)
    assert result.accepted_by_gate
    assert result.success
    assert result.num_leaf_calls == 2


def test_oracle_blind_gates_do_not_use_oracle_for_acceptance(tmp_path):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    wrong_answer = not bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id="oracle-blind-test",
        benchmarks=[],
        variants=[HarnessVariant.H3],
        budget=BudgetConfig(max_retries=0, max_leaf_calls_per_task=1),
        evaluation={"oracle_guided_acceptance": False},
    )
    client = ScriptedClient({
        task.task_id: {
            "task_id": task.task_id,
            "answer": json.dumps({"answer": wrong_answer}),
            "artifacts": ["answer.json"],
            "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
            "self_assessment": {},
            "done": True,
        }
    })
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.H3, store, event_log, state)

    assert result.accepted_by_gate
    assert not result.success
    assert "answer_mismatch" in result.failure_reasons
    gate_results = json.loads((run_dir / result.run_path / "gate_results.json").read_text())
    oracle = [item for item in gate_results if item["gate_name"] == "oracle"][0]
    assert oracle["metadata"]["used_for_acceptance"] is False


def test_generic_retry_uses_generic_feedback_without_typed_gate_details(tmp_path):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    correct_answer = bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id="generic-retry-test",
        benchmarks=[],
        variants=[HarnessVariant.GENERIC_RETRY],
        budget=BudgetConfig(max_retries=2, max_leaf_calls_per_task=2),
        evaluation={"oracle_guided_acceptance": False},
    )
    missing_artifact = {
        "task_id": task.task_id,
        "answer": json.dumps({"answer": correct_answer}),
        "artifacts": [],
        "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
        "self_assessment": {},
        "done": True,
    }
    repaired = dict(missing_artifact)
    repaired["artifacts"] = ["answer.json"]
    client = ScriptedClient({task.task_id: [missing_artifact, repaired]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.GENERIC_RETRY, store, event_log, state)

    assert result.success
    assert result.num_leaf_calls == 2
    assert result.num_retries == 1
    retry_context = (run_dir / result.run_path / "context_pack.md").read_text()
    assert "Previous attempt failed acceptance checks" in retry_context
    assert "artifact_missing" not in retry_context


def test_natural_retry_verbalizes_gate_error_without_typed_codes(tmp_path):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    correct_answer = bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id="natural-retry-test",
        benchmarks=[],
        variants=[HarnessVariant.NATURAL_RETRY],
        budget=BudgetConfig(max_retries=2, max_leaf_calls_per_task=2),
        evaluation={"oracle_guided_acceptance": False},
    )
    missing_artifact = {
        "task_id": task.task_id,
        "answer": json.dumps({"answer": correct_answer}),
        "artifacts": [],
        "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
        "self_assessment": {},
        "done": True,
    }
    repaired = dict(missing_artifact)
    repaired["artifacts"] = ["answer.json"]
    client = ScriptedClient({task.task_id: [missing_artifact, repaired]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.NATURAL_RETRY, store, event_log, state)

    assert result.success
    retry_context = (run_dir / result.run_path / "context_pack.md").read_text()
    assert "The artifact check reported" in retry_context
    assert "Required artifact not listed" in retry_context
    assert "artifact_missing" not in retry_context
    assert "artifact.artifact_missing" not in retry_context


def _run_missing_artifact_repair(tmp_path, variant: HarnessVariant):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    correct_answer = bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id=f"{variant.value}-test",
        benchmarks=[],
        variants=[variant],
        budget=BudgetConfig(max_retries=2, max_leaf_calls_per_task=2),
        evaluation={"oracle_guided_acceptance": False},
    )
    missing_artifact = {
        "task_id": task.task_id,
        "answer": json.dumps({"answer": correct_answer}),
        "artifacts": [],
        "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
        "self_assessment": {},
        "done": True,
    }
    repaired = dict(missing_artifact)
    repaired["artifacts"] = ["answer.json"]
    client = ScriptedClient({task.task_id: [missing_artifact, repaired]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, variant, store, event_log, state)
    retry_context = (run_dir / result.run_path / "context_pack.md").read_text()
    return result, retry_context


def test_generic_diagnostics_adds_raw_validation_message_without_typed_payload(tmp_path):
    result, retry_context = _run_missing_artifact_repair(tmp_path, HarnessVariant.GENERIC_DIAGNOSTICS)

    assert result.success
    assert "Raw validation message from artifact" in retry_context
    assert "Required artifact not listed" in retry_context
    assert "artifact.artifact_missing" not in retry_context
    assert '"location"' not in retry_context


def test_typed_label_only_exposes_label_without_message_or_fields(tmp_path):
    result, retry_context = _run_missing_artifact_repair(tmp_path, HarnessVariant.TYPED_LABEL_ONLY)

    assert result.success
    assert "failure_label=artifact.artifact_missing" in retry_context
    assert "Required artifact not listed" not in retry_context
    assert '"location"' not in retry_context
    assert '"expected"' not in retry_context


def test_typed_fields_exposes_location_expected_observed(tmp_path):
    result, retry_context = _run_missing_artifact_repair(tmp_path, HarnessVariant.TYPED_FIELDS)

    assert result.success
    assert "artifact.artifact_missing" in retry_context
    assert "LeafOutput.artifacts" in retry_context
    assert "answer.json" in retry_context
    assert "observed" in retry_context
    assert "Required artifact not listed" not in retry_context


def test_typed_preserve_adds_full_typed_repair_and_preserve_set(tmp_path):
    result, retry_context = _run_missing_artifact_repair(tmp_path, HarnessVariant.TYPED_PRESERVE)

    assert result.success
    assert "artifact.artifact_missing" in retry_context
    assert "LeafOutput.artifacts" in retry_context
    assert "artifact.artifact_missing" in retry_context
    assert "Required artifact not listed" in retry_context
    assert "Preserve-set: keep task_id exactly" in retry_context


def test_retain_generic_uses_candidate_retention_without_typed_repair(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    config = ExperimentConfig(
        experiment_id="retain-generic-test",
        benchmarks=[],
        variants=[HarnessVariant.RETAIN_GENERIC],
        budget=BudgetConfig(max_retries=0, veriharness_k=2, max_leaf_calls_per_task=2),
    )
    bad = {
        "task_id": task.task_id,
        "answer": '{"export_format": "csv", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "bad", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    good = {
        "task_id": task.task_id,
        "answer": '{"export_format": "jsonl", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "good", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    client = ScriptedClient({task.task_id: [bad, good]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, _, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.RETAIN_GENERIC, store, event_log, state)

    assert result.success
    assert result.num_leaf_calls == 2
    assert result.metadata["candidate_retention"] is True
    assert result.metadata["repair_policy"] == "generic"


def test_typed_no_retain_uses_typed_repair_without_candidate_retention(tmp_path):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    correct_answer = bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id="typed-no-retain-test",
        benchmarks=[],
        variants=[HarnessVariant.TYPED_NO_RETAIN],
        budget=BudgetConfig(max_retries=2, veriharness_k=2, max_leaf_calls_per_task=4),
        evaluation={"oracle_guided_acceptance": False},
    )
    missing_artifact = {
        "task_id": task.task_id,
        "answer": json.dumps({"answer": correct_answer}),
        "artifacts": [],
        "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
        "self_assessment": {},
        "done": True,
    }
    repaired = dict(missing_artifact)
    repaired["artifacts"] = ["answer.json"]
    client = ScriptedClient({task.task_id: [missing_artifact, repaired]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.TYPED_NO_RETAIN, store, event_log, state)

    assert result.success
    assert result.num_leaf_calls == 2
    assert result.metadata["candidate_retention"] is False
    retry_context = (run_dir / result.run_path / "context_pack.md").read_text()
    assert "artifact.artifact_missing" in retry_context


def test_targeted_untyped_focuses_one_locus_without_codes(tmp_path):
    task = generate_boolq_tasks(n_tasks=1, seed=1)[0]
    correct_answer = bool(task.hidden_oracle_payload["answer"])
    config = ExperimentConfig(
        experiment_id="targeted-untyped-test",
        benchmarks=[],
        variants=[HarnessVariant.TARGETED_UNTYPED],
        budget=BudgetConfig(max_retries=2, max_leaf_calls_per_task=2),
        evaluation={"oracle_guided_acceptance": False},
    )
    missing_artifact = {
        "task_id": task.task_id,
        "answer": json.dumps({"answer": correct_answer}),
        "artifacts": [],
        "claims": [{"claim": "answer derived from passage", "evidence_refs": [{"source": "passage"}]}],
        "self_assessment": {},
        "done": True,
    }
    repaired = dict(missing_artifact)
    repaired["artifacts"] = ["answer.json"]
    client = ScriptedClient({task.task_id: [missing_artifact, repaired]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, run_dir, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.TARGETED_UNTYPED, store, event_log, state)

    assert result.success
    retry_context = (run_dir / result.run_path / "context_pack.md").read_text()
    assert "Focus first on listing and producing the required artifact" in retry_context
    assert "artifact_missing" not in retry_context


def test_call_budget_caps_veriharness_candidates(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    bad = {
        "task_id": task.task_id,
        "answer": '{"export_format": "csv", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "bad", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    good = {
        "task_id": task.task_id,
        "answer": '{"export_format": "jsonl", "fields": ["id", "value"]}',
        "artifacts": ["answer.json"],
        "claims": [{"claim": "good", "evidence_refs": [{"source": "task"}]}],
        "self_assessment": {},
        "done": True,
    }
    config = ExperimentConfig(
        experiment_id="call-budget-test",
        benchmarks=[],
        variants=[HarnessVariant.H4],
        budget=BudgetConfig(max_retries=2, veriharness_k=2, max_leaf_calls_per_task=2),
    )
    client = ScriptedClient({task.task_id: [bad, bad, good]})
    orch = Orchestrator(config, client=client, run_manager=RunManager(tmp_path))
    _, _, store, event_log, state = orch.run_manager.create(config, config.model_dump())
    result = orch.run_task_variant(task, HarnessVariant.H4, store, event_log, state)

    assert not result.success
    assert result.num_leaf_calls == 2
    assert client.calls[task.task_id] == 2


def test_aggregation_and_plots(tmp_path):
    rows = [
        {
            "experiment_id": "e",
            "task_id": "t1",
            "benchmark": "context_trace",
            "variant": "H0",
            "trace_length": 4,
            "success": True,
            "wrong_claim_accepted": False,
            "constraint_violation": False,
            "premature_stop": False,
            "tokens_in": 10,
            "tokens_out": 5,
            "num_retries": 0,
            "failure_reasons": [],
        },
        {
            "experiment_id": "e",
            "task_id": "t2",
            "benchmark": "context_trace",
            "variant": "H0",
            "trace_length": 8,
            "success": False,
            "wrong_claim_accepted": False,
            "constraint_violation": True,
            "premature_stop": True,
            "tokens_in": 10,
            "tokens_out": 5,
            "num_retries": 0,
            "failure_reasons": ["constraint_forgotten"],
        },
    ]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            import json

            handle.write(json.dumps(row) + "\n")
    aggregate = aggregate_rows(rows)
    assert aggregate["context_overload_slope"]["H0"] == 1.0
    assert aggregate["failure_modes_by_benchmark"]["context_trace"]["H0"]["context_bloat_proxy_rate"] == 0.5
    assert aggregate["failure_modes_by_benchmark"]["context_trace"]["H0"]["self_biased_acceptance_rate"] == 0.5
    assert "context_trace" in aggregate["paired_deltas_by_benchmark"]
    paths = write_plots(run_dir, tmp_path / "figures")
    assert all(Path(path).exists() for path in paths)


def test_compile_workshop_bundle_writes_tables(tmp_path):
    run_dir = tmp_path / "model-run"
    run_dir.mkdir()
    rows = []
    for variant, success in [("H0", False), ("H3", True), ("H4", True)]:
        rows.append({
            "experiment_id": "e",
            "task_id": "task-1",
            "benchmark": "context_trace",
            "variant": variant,
            "model_client": "dummy",
            "model_name": "mock-model",
            "model_provider": "test",
            "model_parameter_count": 1,
            "model_parameter_count_label": "1B",
            "trace_length": 4,
            "success": success,
            "accepted_by_agent": variant == "H0",
            "accepted_by_gate": variant != "H0",
            "premature_stop": variant == "H0",
            "wrong_claim_accepted": False,
            "constraint_violation": variant == "H0",
            "tokens_in": 10,
            "tokens_out": 2,
            "num_leaf_calls": 1,
            "num_retries": 0,
            "wall_time_sec": 0.1,
            "failure_reasons": ["constraint_forgotten"] if variant == "H0" else [],
            "run_path": "artifacts/leaves/example",
        })
    with (run_dir / "results.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")

    summary = compile_workshop_bundle([run_dir], tmp_path / "compiled", expected_rows=3)

    assert summary["rows"] == 3
    assert (tmp_path / "compiled" / "workshop_results.md").exists()
    assert (tmp_path / "compiled" / "variant_summary.csv").exists()
    text = (tmp_path / "compiled" / "baseline_comparison.md").read_text(encoding="utf-8")
    assert "AutoResearch-style self-accept harness" in text
