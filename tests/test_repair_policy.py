from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.benchmarks.provenance_bias import generate_provenance_bias_tasks
from veriharness.core.context_pack import build_context_pack
from veriharness.core.repair_policy import build_retry_feedback
from veriharness.core.types import (
    BudgetConfig,
    GateFailure,
    GateResult,
    HarnessVariant,
    LeafOutput,
    LeafRequest,
)
from veriharness.leaves.prompts import render_leaf_prompt


def test_context_trace_repair_feedback_names_missing_fields():
    task = generate_context_trace_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H3, BudgetConfig())
    output = LeafOutput(
        task_id=task.task_id,
        answer='{"export_format":"jsonl"}',
        artifacts=["answer.json"],
        done=True,
    )
    feedback = build_retry_feedback(
        task,
        pack,
        output,
        [
            GateResult(
                gate_name="oracle",
                passed=False,
                failures=[GateFailure(code="required_field_missing", message="Required fields missing.")],
            )
        ],
    )
    assert any("id, value" in item for item in feedback)
    assert any('"fields"' in item for item in feedback)


def test_repair_feedback_is_rendered_prominently():
    task = generate_provenance_bias_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.H3, BudgetConfig())
    request = LeafRequest(
        context_pack=pack,
        task=task,
        retry_feedback=["Choose action=reject or action=repair."],
    )
    prompt = render_leaf_prompt(request)
    assert "Repair guidance from external gates" in prompt
    assert "Choose action=reject or action=repair" in prompt
