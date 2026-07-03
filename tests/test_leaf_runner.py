from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.context_pack import build_context_pack
from veriharness.core.types import BudgetConfig, HarnessVariant, LeafRequest
from veriharness.leaves.leaf_runner import LeafRunner
from veriharness.llm.scripted_client import ScriptedClient


def test_leaf_runner_saves_transcript_and_output(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H3, BudgetConfig())
    client = ScriptedClient({
        task.task_id: {
            "task_id": task.task_id,
            "answer": '{"export_format": "jsonl", "fields": ["id", "value"]}',
            "artifacts": ["answer.json"],
            "claims": [],
            "self_assessment": {},
            "done": True,
        }
    })
    store = ArtifactStore(tmp_path, "run")
    output = LeafRunner(client, store).run(LeafRequest(context_pack=pack, task=task), "leaf")
    assert output.done
    assert store.path("leaf/transcript.txt").exists()
    assert store.path("leaf/leaf_output.json").exists()


def test_invalid_json_creates_synthetic_failed_output(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H3, BudgetConfig())
    store = ArtifactStore(tmp_path, "run")
    output = LeafRunner(ScriptedClient({task.task_id: "not-json"}), store).run(
        LeafRequest(context_pack=pack, task=task),
        "leaf",
    )
    assert not output.done
    assert "parse_error" in output.self_assessment


def test_leaf_runner_stringifies_nested_answer_payload(tmp_path):
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H3, BudgetConfig())
    client = ScriptedClient({
        task.task_id: {
            "task_id": task.task_id,
            "answer": {"export_format": "jsonl", "fields": ["id", "value"]},
            "artifacts": ["answer.json"],
            "claims": [],
            "self_assessment": {},
            "done": True,
        }
    })
    store = ArtifactStore(tmp_path, "run")
    output = LeafRunner(client, store).run(LeafRequest(context_pack=pack, task=task), "leaf")
    assert output.answer == '{"export_format": "jsonl", "fields": ["id", "value"]}'
