from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.core.context_pack import build_context_pack
from veriharness.core.types import BudgetConfig, HarnessVariant


def test_h2_uses_state_lifted_context_without_raw_trace():
    task = generate_context_trace_tasks(n_tasks=1, trace_lengths=[8], seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H2, BudgetConfig())
    assert "raw_trace" not in pack.current_state
    assert any("jsonl" in fact for fact in pack.accepted_facts)
    assert any("csv" in fact for fact in pack.rejected_facts)


def test_h0_contains_raw_trace():
    task = generate_context_trace_tasks(n_tasks=1, trace_lengths=[8], seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.SELF_ACCEPT, BudgetConfig())
    assert "raw_trace" in pack.current_state
