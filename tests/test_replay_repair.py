import json

from veriharness.benchmarks import public_nlp
from veriharness.core.run_manager import RunManager
from veriharness.core.types import BenchmarkConfig, BudgetConfig, ExperimentConfig, HarnessVariant
from veriharness.experiments.aggregate import read_results
from veriharness.experiments.replay_repair import ReplayRepairRunner, frozen_failed_output
from veriharness.llm.dummy_client import DummyClient


def test_frozen_failed_output_is_oracle_negative():
    task = public_nlp.TaskSpec(
        task_id="mc-fake",
        family="multiple_choice",
        description="Fake multiple-choice task.",
        input_payload={
            "choices": [
                {"label": "A", "text": "right"},
                {"label": "B", "text": "wrong"},
            ]
        },
        hidden_oracle_payload={
            "oracle_type": "multiple_choice",
            "answer_label": "A",
            "answer_text": "right",
            "required_artifacts": ["answer.json"],
            "require_evidence": False,
        },
    )

    output = frozen_failed_output(task)

    assert json.loads(output.answer)["answer"] == "B"
    assert output.done is True


def test_replay_repair_runner_uses_one_repair_call_per_variant(tmp_path, monkeypatch):
    rows = [
        {
            "row_idx": 7,
            "row": {
                "question": "What gas do plants absorb?",
                "correct_answer": "carbon dioxide",
                "distractor1": "oxygen",
                "distractor2": "helium",
                "distractor3": "argon",
                "support": "Plants absorb carbon dioxide during photosynthesis.",
            },
        }
    ]
    monkeypatch.setattr(public_nlp, "load_hf_rows", lambda *args, **kwargs: rows)
    config = ExperimentConfig(
        experiment_id="replay-repair-smoke",
        benchmarks=[
            BenchmarkConfig(name="boolq", n_tasks=1, seeds=[1]),
            BenchmarkConfig(name="sciq", n_tasks=1, seeds=[1]),
            BenchmarkConfig(name="mini_workflow", n_tasks=1, seeds=[1]),
        ],
        variants=[HarnessVariant.GENERIC_RETRY, HarnessVariant.TYPED_FIELDS],
        model={"client": "dummy", "provider": "test", "model_name": "dummy"},
        budget=BudgetConfig(max_retries=1, veriharness_k=1, max_leaf_calls_per_task=1),
    )

    run_dir = ReplayRepairRunner(config, client=DummyClient(), run_manager=RunManager(tmp_path)).run()
    results = read_results(run_dir)
    frozen_rows = [
        json.loads(line)
        for line in (run_dir / "frozen_failures.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(frozen_rows) == 3
    assert len(results) == 6
    assert all(row["num_leaf_calls"] == 1 for row in results)
    assert all(row["num_retries"] == 1 for row in results)
    assert all(row["metadata"]["mode"] == "replay_repair" for row in results)
    assert all(row["metadata"]["frozen_failure_reasons"] for row in results)
    assert all((run_dir / row["metadata"]["frozen_failure_path"] / "leaf_output.json").exists() for row in results)
    assert all(row["success"] for row in results)
