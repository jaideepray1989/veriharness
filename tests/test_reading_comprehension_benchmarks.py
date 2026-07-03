from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.types import LeafOutput, TaskSpec


def test_boolq_oracle_accepts_json_boolean():
    task = TaskSpec(
        task_id="boolq-fake",
        family="boolq",
        description="Fake BoolQ task.",
        hidden_oracle_payload={"oracle_type": "boolq", "answer": True},
    )
    output = LeafOutput(task_id=task.task_id, answer='{"answer": true}', done=True)
    assert evaluate_oracle(task, output).passed


def test_boolq_oracle_rejects_wrong_boolean():
    task = TaskSpec(
        task_id="boolq-fake",
        family="boolq",
        description="Fake BoolQ task.",
        hidden_oracle_payload={"oracle_type": "boolq", "answer": False},
    )
    output = LeafOutput(task_id=task.task_id, answer='{"answer": true}', done=True)
    result = evaluate_oracle(task, output)
    assert not result.passed
    assert any(failure.code == "answer_mismatch" for failure in result.failures)


def test_squad_oracle_accepts_high_overlap_answer():
    task = TaskSpec(
        task_id="squad-fake",
        family="squad",
        description="Fake SQuAD task.",
        hidden_oracle_payload={
            "oracle_type": "squad",
            "answers": ["Super Bowl 50"],
            "min_f1": 0.8,
        },
    )
    output = LeafOutput(task_id=task.task_id, answer='{"answer": "the Super Bowl 50"}', done=True)
    assert evaluate_oracle(task, output).passed


def test_squad_oracle_rejects_unrelated_answer():
    task = TaskSpec(
        task_id="squad-fake",
        family="squad",
        description="Fake SQuAD task.",
        hidden_oracle_payload={
            "oracle_type": "squad",
            "answers": ["Denver Broncos"],
            "min_f1": 0.8,
        },
    )
    output = LeafOutput(task_id=task.task_id, answer='{"answer": "Carolina Panthers"}', done=True)
    result = evaluate_oracle(task, output)
    assert not result.passed
    assert any(failure.code == "answer_mismatch" for failure in result.failures)
