from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.types import Claim, EvidenceRef, LeafOutput
from veriharness.gates.gate_stack import GateStack


def test_gate_stack_schema_failure(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    store = ArtifactStore(tmp_path, "run")
    output = LeafOutput(task_id=task.task_id, answer="", self_assessment={"parse_error": "bad"}, done=True)
    passed, results = GateStack().evaluate(task, output, store, "leaf")
    assert not passed
    assert any(failure.code == "schema_invalid" for result in results for failure in result.failures)


def test_missing_artifact_failure(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    store = ArtifactStore(tmp_path, "run")
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"export_format": "jsonl", "fields": ["id", "value"]}',
        artifacts=[],
        claims=[Claim(claim="ok", evidence_refs=[EvidenceRef(source="task")])],
        done=True,
    )
    passed, results = GateStack().evaluate(task, output, store, "leaf")
    assert not passed
    assert any(failure.code == "artifact_missing" for result in results for failure in result.failures)


def test_claim_without_evidence_failure(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    store = ArtifactStore(tmp_path, "run")
    store.write_text("leaf/answer.json", "{}")
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"export_format": "jsonl", "fields": ["id", "value"]}',
        artifacts=["answer.json"],
        claims=[Claim(claim="ok")],
        done=True,
    )
    passed, results = GateStack().evaluate(task, output, store, "leaf")
    assert not passed
    assert any(failure.code == "claim_without_evidence" for result in results for failure in result.failures)


def test_all_gates_pass(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    store = ArtifactStore(tmp_path, "run")
    store.write_text("leaf/answer.json", "{}")
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"export_format": "jsonl", "fields": ["id", "value"]}',
        artifacts=["answer.json"],
        claims=[Claim(claim="ok", evidence_refs=[EvidenceRef(source="task")])],
        done=True,
    )
    passed, _ = GateStack().evaluate(task, output, store, "leaf")
    assert passed


def test_llm_verifier_cannot_override_deterministic_failure(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    store = ArtifactStore(tmp_path, "run")
    store.write_text("leaf/answer.json", "{}")
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"export_format": "csv", "fields": ["id", "value"]}',
        artifacts=["answer.json"],
        claims=[Claim(claim="bad", evidence_refs=[EvidenceRef(source="task")])],
        done=True,
    )
    passed, results = GateStack().evaluate(task, output, store, "leaf")
    assert not passed
    assert any(result.gate_name == "deterministic" and not result.passed for result in results)
