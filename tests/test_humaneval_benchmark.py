from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.context_pack import build_context_pack
from veriharness.core.types import BudgetConfig, HarnessVariant, LeafOutput, LeafRequest, TaskSpec
from veriharness.leaves.prompts import render_leaf_prompt


def _fake_humaneval_task() -> TaskSpec:
    prompt = "def add_one(x):\n    \"\"\"Return x plus one.\"\"\"\n"
    test = "def check(candidate):\n    assert candidate(1) == 2\n    assert candidate(-1) == 0\n"
    return TaskSpec(
        task_id="humaneval-fake",
        family="humaneval",
        description="Fake HumanEval task.",
        input_payload={"prompt": prompt, "entry_point": "add_one"},
        hidden_oracle_payload={
            "oracle_type": "humaneval",
            "prompt": prompt,
            "test": test,
            "entry_point": "add_one",
            "timeout_seconds": 2,
        },
    )


def test_humaneval_oracle_passes_valid_code():
    task = _fake_humaneval_task()
    output = LeafOutput(
        task_id=task.task_id,
        answer="def add_one(x):\n    return x + 1\n",
        artifacts=["solution.py"],
        done=True,
    )
    result = evaluate_oracle(task, output)
    assert result.passed


def test_humaneval_oracle_reports_unit_test_failure():
    task = _fake_humaneval_task()
    output = LeafOutput(
        task_id=task.task_id,
        answer="def add_one(x):\n    return x\n",
        artifacts=["solution.py"],
        done=True,
    )
    result = evaluate_oracle(task, output)
    assert not result.passed
    assert any(failure.code == "unit_test_failed" for failure in result.failures)
    assert any("assert candidate" in failure.message for failure in result.failures)


def test_humaneval_candidate_prompts_use_different_strategies():
    task = _fake_humaneval_task()
    pack = build_context_pack(task, HarnessVariant.H4, BudgetConfig(veriharness_k=2))
    prompt_a = render_leaf_prompt(
        LeafRequest(context_pack=pack, task=task, candidate_id="candidate-0")
    )
    prompt_b = render_leaf_prompt(
        LeafRequest(context_pack=pack, task=task, candidate_id="candidate-1")
    )
    assert "Official HumanEval prompt" in prompt_a
    assert "candidate strategy" in prompt_a
    assert prompt_a != prompt_b
