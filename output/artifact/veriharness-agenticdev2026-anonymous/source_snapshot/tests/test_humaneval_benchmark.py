from veriharness.benchmarks.humaneval import _public_test_prefix, generate_humaneval_public_tasks
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.context_pack import build_context_pack
from veriharness.core.types import BudgetConfig, HarnessVariant, LeafOutput, LeafRequest, TaskSpec
from veriharness.leaves.prompts import render_leaf_prompt
from veriharness.gates.public_test_gate import PublicTestGate


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
    pack = build_context_pack(task, HarnessVariant.TYPED_REPAIR_RETAIN, BudgetConfig(veriharness_k=2))
    prompt_a = render_leaf_prompt(
        LeafRequest(context_pack=pack, task=task, candidate_id="candidate-0")
    )
    prompt_b = render_leaf_prompt(
        LeafRequest(context_pack=pack, task=task, candidate_id="candidate-1")
    )
    assert "Official HumanEval prompt" in prompt_a
    assert "candidate strategy" in prompt_a
    assert prompt_a != prompt_b


def test_public_test_prefix_keeps_setup_and_first_assertion():
    test = "def check(candidate):\n    value = candidate(1)\n    assert value == 2\n    assert candidate(2) == 3\n"
    public = _public_test_prefix(test)

    assert "value = candidate(1)" in public
    assert "assert value == 2" in public
    assert "candidate(2)" not in public


def test_humaneval_public_gate_exposes_one_assertion_and_hidden_oracle_scores_all():
    task = _fake_humaneval_task().model_copy(deep=True)
    task.family = "humaneval_public"
    task.input_payload["public_test"] = _public_test_prefix(task.hidden_oracle_payload["test"])
    output = LeafOutput(
        task_id=task.task_id,
        answer="def add_one(x):\n    return 2 if x == 1 else x\n",
        artifacts=["solution.py"],
        done=True,
    )

    assert PublicTestGate().evaluate(task, output, store=None, leaf_dir="").passed
    assert not evaluate_oracle(task, output).passed


def test_humaneval_public_selection_is_deterministic_and_records_rule():
    first = generate_humaneval_public_tasks(n_tasks=3, seed=1)
    second = generate_humaneval_public_tasks(n_tasks=3, seed=1)

    assert [task.task_id for task in first] == [task.task_id for task in second]
    assert all(task.metadata["public_test_rule"] for task in first)
