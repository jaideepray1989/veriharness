from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.types import LeafOutput


def test_context_trace_generation_is_deterministic():
    a = generate_context_trace_tasks(n_tasks=10, trace_lengths=[4, 8], seed=1)
    b = generate_context_trace_tasks(n_tasks=10, trace_lengths=[4, 8], seed=1)
    assert [task.model_dump() for task in a] == [task.model_dump() for task in b]
    assert len(a) == 10


def test_context_trace_oracle_flags_known_outputs():
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    good = LeafOutput(task_id=task.task_id, answer='{"export_format": "jsonl", "fields": ["id", "value"]}')
    bad = LeafOutput(task_id=task.task_id, answer='{"export_format": "csv", "fields": ["id", "value"]}')
    assert evaluate_oracle(task, good).passed
    assert not evaluate_oracle(task, bad).passed
