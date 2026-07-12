import json

from veriharness.benchmarks import external_benchmarks
from veriharness.benchmarks.oracles import evaluate_oracle
from veriharness.core.types import LeafOutput


def test_swebench_lite_generator_builds_patch_task(monkeypatch):
    rows = [
        {
            "row_idx": 0,
            "row": {
                "repo": "astropy/astropy",
                "instance_id": "astropy__astropy-12907",
                "base_commit": "abc123",
                "patch": "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n",
                "test_patch": "diff --git a/test.py b/test.py\n",
                "problem_statement": "Fix the bug.",
                "hints_text": "",
                "FAIL_TO_PASS": '["test_bug"]',
                "PASS_TO_PASS": '["test_old"]',
            },
        }
    ]
    monkeypatch.setattr(external_benchmarks, "load_hf_rows", lambda *args, **kwargs: rows)

    task = external_benchmarks.generate_swebench_tasks("swebench_lite", n_tasks=1, seed=1)[0]

    assert task.family == "swebench_patch"
    assert task.metadata["benchmark"] == "swebench_lite"
    assert task.hidden_oracle_payload["external_eval"]["required"] is True
    assert task.input_payload["fail_to_pass"] == ["test_bug"]


def test_swebench_patch_oracle_accepts_reference_patch():
    patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    from veriharness.core.types import TaskSpec

    spec = TaskSpec(
        task_id="swebench-fake",
        family="swebench_patch",
        description="Fake SWE-bench task.",
        hidden_oracle_payload={"oracle_type": "swebench_patch", "reference_patch": patch},
    )
    output = LeafOutput(task_id=spec.task_id, answer=patch, artifacts=["patch.diff"], done=True)

    result = evaluate_oracle(spec, output)

    assert result.passed
    assert result.metadata["external_eval_required"] is True


def test_ds1000_generator_and_oracle_execute_reference_code(monkeypatch):
    code_context = """
import copy

def generate_test_case(test_case_id):
    test_input = 2
    expected_result = 3
    return test_input, expected_result

exec_context = \"\"\"
test_input = test_input
[insert]
\"\"\"

def test_execution(solution: str):
    code = exec_context.replace("[insert]", solution)
    test_input, expected_result = generate_test_case(1)
    test_env = {"test_input": test_input}
    exec(code, test_env)
    assert test_env["result"] == expected_result
"""
    rows = [
        {
            "row_idx": 0,
            "row": {
                "prompt": "Set result to input plus one.",
                "reference_code": "result = test_input + 1",
                "metadata": {"problem_id": 3, "library": "Python", "test_case_cnt": 1},
                "code_context": code_context,
            },
        }
    ]
    monkeypatch.setattr(external_benchmarks, "load_hf_rows", lambda *args, **kwargs: rows)

    task = external_benchmarks.generate_ds1000_tasks(n_tasks=1, seed=1)[0]
    output = LeafOutput(task_id=task.task_id, answer="result = test_input + 1", artifacts=["solution.py"], done=True)

    assert task.family == "ds1000"
    assert evaluate_oracle(task, output).passed


def test_mlagentbench_generator_and_manifest_oracle(monkeypatch):
    monkeypatch.setattr(
        external_benchmarks,
        "fetch_mlagentbench_research_problem",
        lambda task_name: f"Improve {task_name}.",
    )
    task = external_benchmarks.generate_mlagentbench_tasks(n_tasks=1, seed=1)[0]
    manifest = {
        "task_name": task.input_payload["task_name"],
        "train_command": "python train.py",
        "eval_command": "python -m MLAgentBench.eval",
        "expected_artifacts": ["submission.csv"],
    }
    output = LeafOutput(
        task_id=task.task_id,
        answer=json.dumps(manifest),
        artifacts=["research_plan.json"],
        done=True,
    )

    result = evaluate_oracle(task, output)

    assert task.family == "mlagentbench"
    assert result.passed
    assert result.metadata["external_eval_required"] is True
