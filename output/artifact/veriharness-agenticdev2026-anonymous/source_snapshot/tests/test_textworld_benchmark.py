import json

from veriharness.benchmarks.textworld import generate_textworld_tasks
from veriharness.core.context_pack import build_context_pack
from veriharness.core.repair_policy import build_typed_field_feedback
from veriharness.core.types import BudgetConfig, GateFailure, GateResult, HarnessVariant, LeafOutput
from veriharness.gates.textworld_gate import TextWorldGate


def _descriptor(payload):
    return {
        "game_path": f"/tmp/{payload['game_seed']}.z8",
        "game_seed": payload["game_seed"],
        "objective": "Reach the test objective.",
        "description": "You are in a test room.",
        "inventory": "You are carrying nothing.",
        "max_score": 1,
    }


def test_textworld_generator_uses_preregistered_unique_seeds(monkeypatch, tmp_path):
    monkeypatch.setattr("veriharness.benchmarks.textworld._bridge", lambda operation, payload, timeout: _descriptor(payload))

    tasks = generate_textworld_tasks(n_tasks=200, seed=1, cache_root=tmp_path)

    assert len(tasks) == 200
    assert len({task.metadata["game_seed"] for task in tasks}) == 200
    assert {task.metadata["seed_manifest"] for task in tasks} == {"textworld-preregistered-v1"}
    assert all(task.metadata["benchmark"] == "textworld" for task in tasks)


def test_textworld_gate_exposes_typed_action_locus(monkeypatch):
    monkeypatch.setattr("veriharness.benchmarks.textworld._bridge", lambda operation, payload, timeout: _descriptor(payload))
    task = generate_textworld_tasks(n_tasks=1, seed=1, cache_root="/tmp")
    task = task[0]
    output = LeafOutput(
        task_id=task.task_id,
        answer=json.dumps({"commands": ["dance"]}),
        artifacts=["action_plan.json"],
    )
    failure = GateFailure(
        code="action_invalid",
        message="Command 0 is not admissible in the current game state.",
        details={
            "location": "LeafOutput.answer.commands[0]",
            "expected": ["go north"],
            "observed": "dance",
        },
    )
    result = GateResult(gate_name="oracle", passed=False, failures=[failure])
    monkeypatch.setattr("veriharness.gates.textworld_gate.textworld_oracle", lambda _task, _output: result)

    gate_result = TextWorldGate().evaluate(task, output, store=None, leaf_dir="")
    pack = build_context_pack(task, HarnessVariant.TYPED_FIELDS, BudgetConfig())
    feedback = build_typed_field_feedback(task, pack, output, [gate_result])

    assert gate_result.gate_name == "textworld"
    assert '"location": "LeafOutput.answer.commands[0]"' in feedback[1]
    assert '"observed": "dance"' in feedback[1]
