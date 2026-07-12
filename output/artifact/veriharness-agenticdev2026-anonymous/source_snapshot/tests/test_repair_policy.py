from veriharness.benchmarks.context_trace import generate_context_trace_tasks
from veriharness.benchmarks.provenance_bias import generate_provenance_bias_tasks
from veriharness.core.context_pack import build_context_pack
from veriharness.core.repair_policy import (
    build_location_observed_feedback,
    build_retry_feedback,
    build_same_info_natural_feedback,
    build_typed_field_feedback,
)
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
    pack = build_context_pack(task, HarnessVariant.GATED_RESAMPLE, BudgetConfig())
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
    pack = build_context_pack(task, HarnessVariant.GATED_RESAMPLE, BudgetConfig())
    request = LeafRequest(
        context_pack=pack,
        task=task,
        retry_feedback=["Choose action=reject or action=repair."],
    )
    prompt = render_leaf_prompt(request)
    assert "Repair guidance from external gates" in prompt
    assert "Choose action=reject or action=repair" in prompt


def test_same_info_natural_matches_typed_fields_without_typed_structure():
    task = generate_provenance_bias_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.SAME_INFO_NATURAL, BudgetConfig())
    output = LeafOutput(task_id=task.task_id, answer='{"action":"accept"}', done=True)
    result = GateResult(
        gate_name="test_gate",
        passed=False,
        failures=[
            GateFailure(
                code="json_field_mismatch",
                message="action was rejected",
                details={"location": "LeafOutput.answer.action", "expected": ["reject", "repair"], "observed": "accept"},
            )
        ],
    )

    typed = "\n".join(build_typed_field_feedback(task, pack, output, [result]))
    natural = "\n".join(build_same_info_natural_feedback(task, pack, output, [result]))

    for value in ("LeafOutput.answer.action", "reject", "repair", "accept"):
        assert value in typed
        assert value in natural
    assert "typed_failure=" not in natural
    assert '"label"' not in natural
    assert '"location"' not in natural


def test_location_observed_omits_expected_alternatives():
    task = generate_provenance_bias_tasks(n_tasks=1, seed=1)[0]
    pack = build_context_pack(task, HarnessVariant.LOCATION_OBSERVED, BudgetConfig())
    output = LeafOutput(task_id=task.task_id, answer='{"action":"accept"}', done=True)
    result = GateResult(
        gate_name="test_gate",
        passed=False,
        failures=[
            GateFailure(
                code="json_field_mismatch",
                message="action was rejected",
                details={"location": "LeafOutput.answer.action", "expected": ["reject", "repair"], "observed": "accept"},
            )
        ],
    )

    feedback = "\n".join(build_location_observed_feedback(task, pack, output, [result]))

    assert '"label": "test_gate.json_field_mismatch"' in feedback
    assert '"location": "LeafOutput.answer.action"' in feedback
    assert '"observed": "accept"' in feedback
    assert '"expected"' not in feedback
    assert '["reject", "repair"]' not in feedback
    assert '"repair"' not in feedback
