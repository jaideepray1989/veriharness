import json
from pathlib import Path

from veriharness.experiments.official_runners import (
    build_mlagentbench_commands,
    build_swebench_command,
    export_mlagentbench_manifests,
    export_swebench_predictions,
    write_command_plan,
)


def test_export_swebench_predictions_from_leaf_artifact(tmp_path: Path):
    run_dir = tmp_path / "run"
    leaf_dir = run_dir / "artifacts/leaves/H4/swebench_lite/seed_1/swebench_lite-django__django-13321/attempt_0/candidate-0"
    leaf_dir.mkdir(parents=True)
    patch = "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-old\n+new\n"
    (leaf_dir / "patch.diff").write_text(patch, encoding="utf-8")
    (leaf_dir / "leaf_output.json").write_text(
        json.dumps({"task_id": "swebench_lite-django__django-13321", "answer": patch, "artifacts": ["patch.diff"], "done": True}),
        encoding="utf-8",
    )
    row = {
        "task_id": "swebench_lite-django__django-13321",
        "benchmark": "swebench_lite",
        "variant": "H4",
        "model_client": "dummy",
        "model_name": "dummy",
        "success": True,
        "run_path": str(leaf_dir.relative_to(run_dir)),
    }
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    out = tmp_path / "predictions.jsonl"
    summary = export_swebench_predictions(run_dir, out, variant="H4", benchmark="swebench_lite")
    prediction = json.loads(out.read_text(encoding="utf-8"))

    assert summary["n_predictions"] == 1
    assert prediction["instance_id"] == "django__django-13321"
    assert prediction["model_name_or_path"] == "veriharness-H4-dummy"
    assert prediction["model_patch"] == patch


def test_build_swebench_official_command():
    command = build_swebench_command(
        Path("predictions.jsonl"),
        dataset_name="princeton-nlp/SWE-bench_Lite",
        run_id="paper_h4",
        python_bin="python3.10",
        max_workers=2,
        instance_ids=["django__django-13321"],
    )

    assert command[:3] == ["python3.10", "-m", "swebench.harness.run_evaluation"]
    assert "--predictions_path" in command
    assert "predictions.jsonl" in command
    assert command[-2:] == ["--instance_ids", "django__django-13321"]


def test_export_mlagentbench_manifest_from_leaf_output(tmp_path: Path):
    run_dir = tmp_path / "run"
    leaf_dir = run_dir / "artifacts/leaves/H4/mlagentbench/seed_1/mlagentbench-cifar10/attempt_0/candidate-0"
    leaf_dir.mkdir(parents=True)
    manifest = {
        "task_name": "cifar10",
        "train_command": "python train.py",
        "eval_command": "python -m MLAgentBench.eval",
        "expected_artifacts": ["submission.csv"],
    }
    (leaf_dir / "leaf_output.json").write_text(
        json.dumps({"task_id": "mlagentbench-cifar10", "answer": json.dumps(manifest), "artifacts": ["research_plan.json"], "done": True}),
        encoding="utf-8",
    )
    row = {
        "task_id": "mlagentbench-cifar10",
        "benchmark": "mlagentbench",
        "variant": "H4",
        "success": True,
        "run_path": str(leaf_dir.relative_to(run_dir)),
    }
    (run_dir / "results.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")

    summary = export_mlagentbench_manifests(run_dir, tmp_path / "manifests", variant="H4")
    exported = json.loads((tmp_path / "manifests/cifar10/research_plan.json").read_text(encoding="utf-8"))

    assert summary["n_manifests"] == 1
    assert exported["task_name"] == "cifar10"
    assert exported["expected_artifacts"] == ["submission.csv"]


def test_build_mlagentbench_plan_and_script(tmp_path: Path):
    plan = build_mlagentbench_commands(
        ["cifar10"],
        python_bin="python3.10",
        task_python="python3.10",
        log_root=Path("logs"),
        work_root=Path("workspace"),
        eval_root=Path("eval"),
        agent_type="Agent",
    )
    written = write_command_plan(plan, tmp_path / "mlagentbench_plan.json")
    script = Path(written["script_path"]).read_text(encoding="utf-8")

    assert [step["phase"] for step in plan] == ["prepare", "runner", "eval"]
    assert plan[1]["command"][:3] == ["python3.10", "-u", "-m"]
    assert "MLAgentBench.runner" in plan[1]["command"]
    assert "MLAgentBench.eval" in script
