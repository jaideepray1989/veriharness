from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.benchmarks.provenance_bias import generate_provenance_bias_tasks
from veriharness.core.types import LeafOutput


def test_provenance_bias_generation_reuses_same_wrong_claim():
    tasks = generate_provenance_bias_tasks(n_tasks=10, seed=1)
    claims = {task.input_payload["wrong_claim"] for task in tasks}
    labels = {task.input_payload["provenance_label"] for task in tasks}
    assert len(claims) == 1
    assert "own_previous_answer" in labels


def test_provenance_oracle_flags_wrong_acceptance():
    task = generate_provenance_bias_tasks(n_tasks=1, seed=1)[0]
    bad = LeafOutput(task_id=task.task_id, answer='{"action": "accept"}')
    good = LeafOutput(task_id=task.task_id, answer='{"action": "reject"}')
    assert not evaluate_oracle(task, bad).passed
    assert evaluate_oracle(task, good).passed
