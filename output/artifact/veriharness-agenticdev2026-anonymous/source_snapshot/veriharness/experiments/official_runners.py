from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from veriharness.core.types import canonical_variant_name
from veriharness.experiments.aggregate import read_results

SWE_BENCH_DATASETS = {
    "swebench_lite": "princeton-nlp/SWE-bench_Lite",
    "swebench_verified": "princeton-nlp/SWE-bench_Verified",
}


def export_swebench_predictions(
    run_dir: Path,
    out_path: Path,
    *,
    variant: str,
    benchmark: str,
    model_name: Optional[str] = None,
    include_empty: bool = True,
    only_success: bool = False,
) -> Dict[str, Any]:
    """Export VeriHarness patch artifacts to SWE-bench official JSONL format."""
    run_dir = Path(run_dir)
    if benchmark not in SWE_BENCH_DATASETS:
        raise ValueError(f"unsupported SWE-bench benchmark: {benchmark}")
    variant = canonical_variant_name(variant)

    predictions: List[Dict[str, str]] = []
    skipped = 0
    for row in read_results(run_dir):
        if row.get("variant") != variant or row.get("benchmark") != benchmark:
            continue
        if only_success and not row.get("success"):
            skipped += 1
            continue
        patch = _leaf_answer(run_dir, row, preferred_artifact="patch.diff")
        if not include_empty and not patch.strip():
            skipped += 1
            continue
        predictions.append(
            {
                "instance_id": _swebench_instance_id(row),
                "model_name_or_path": model_name or _model_label(row, variant),
                "model_patch": patch,
            }
        )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for prediction in predictions:
            handle.write(json.dumps(prediction, sort_keys=True) + "\n")

    return {
        "run_dir": str(run_dir),
        "out_path": str(out_path),
        "variant": variant,
        "benchmark": benchmark,
        "dataset_name": SWE_BENCH_DATASETS[benchmark],
        "n_predictions": len(predictions),
        "skipped": skipped,
    }


def build_swebench_command(
    predictions_path: Path,
    *,
    dataset_name: str,
    run_id: str,
    python_bin: str = sys.executable,
    max_workers: int = 4,
    timeout: int = 1800,
    cache_level: str = "env",
    report_dir: Optional[Path] = None,
    instance_ids: Optional[Sequence[str]] = None,
    modal: bool = False,
) -> List[str]:
    command = [
        python_bin,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset_name,
        "--predictions_path",
        str(predictions_path),
        "--max_workers",
        str(max_workers),
        "--run_id",
        run_id,
        "--timeout",
        str(timeout),
        "--cache_level",
        cache_level,
    ]
    if report_dir is not None:
        command.extend(["--report_dir", str(report_dir)])
    if instance_ids:
        command.extend(["--instance_ids", *[str(item) for item in instance_ids]])
    if modal:
        command.extend(["--modal", "true"])
    return command


def run_command(command: Sequence[str], *, cwd: Optional[Path] = None, dry_run: bool = True) -> Dict[str, Any]:
    payload = {
        "command": list(command),
        "shell_command": shlex.join([str(item) for item in command]),
        "cwd": str(cwd) if cwd else None,
        "dry_run": dry_run,
    }
    if dry_run:
        return payload
    completed = subprocess.run(command, cwd=cwd, text=True, check=False)
    payload["returncode"] = completed.returncode
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, command)
    return payload


def export_mlagentbench_manifests(
    run_dir: Path,
    out_dir: Path,
    *,
    variant: str,
    include_unsuccessful: bool = False,
) -> Dict[str, Any]:
    """Materialize VeriHarness MLAgentBench plans for inspection and official runner setup."""
    run_dir = Path(run_dir)
    out_dir = Path(out_dir)
    variant = canonical_variant_name(variant)
    out_dir.mkdir(parents=True, exist_ok=True)

    index: List[Dict[str, Any]] = []
    skipped = 0
    for row in read_results(run_dir):
        if row.get("variant") != variant or row.get("benchmark") != "mlagentbench":
            continue
        if not include_unsuccessful and not row.get("success"):
            skipped += 1
            continue
        answer = _leaf_answer(run_dir, row, preferred_artifact="research_plan.json")
        manifest = _parse_manifest(answer)
        task_name = str(manifest.get("task_name") or _mlagentbench_task_name(row))
        task_dir = out_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = task_dir / "research_plan.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index.append(
            {
                "task_name": task_name,
                "task_id": row.get("task_id"),
                "variant": variant,
                "manifest_path": str(manifest_path),
                "run_path": row.get("run_path", ""),
                "success": bool(row.get("success")),
            }
        )

    index_path = out_dir / "manifest_index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "variant": variant,
        "n_manifests": len(index),
        "skipped": skipped,
        "index_path": str(index_path),
    }


def build_mlagentbench_commands(
    tasks: Iterable[str],
    *,
    python_bin: str = sys.executable,
    task_python: str = sys.executable,
    log_root: Path = Path("mlagentbench_logs"),
    work_root: Path = Path("workspace"),
    eval_root: Path = Path("mlagentbench_eval"),
    device: str = "0",
    agent_type: Optional[str] = "Agent",
    llm_name: Optional[str] = None,
    edit_script_llm_name: Optional[str] = None,
    fast_llm_name: Optional[str] = None,
    prepare: bool = True,
) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    for task in [item for item in tasks if item]:
        task_log_dir = Path(log_root) / task
        task_work_dir = Path(work_root) / task
        eval_file = Path(eval_root) / f"{task}.json"
        if prepare:
            plan.append(
                {
                    "task": task,
                    "phase": "prepare",
                    "command": [
                        python_bin,
                        "-u",
                        "-m",
                        "MLAgentBench.prepare_task",
                        task,
                        task_python,
                    ],
                }
            )
        runner = [
            python_bin,
            "-u",
            "-m",
            "MLAgentBench.runner",
            "--python",
            task_python,
            "--task",
            task,
            "--device",
            str(device),
            "--log-dir",
            str(task_log_dir),
            "--work-dir",
            str(task_work_dir),
        ]
        if agent_type:
            runner.extend(["--agent_type", agent_type])
        if llm_name:
            runner.extend(["--llm-name", llm_name])
        if edit_script_llm_name:
            runner.extend(["--edit-script-llm-name", edit_script_llm_name])
        if fast_llm_name:
            runner.extend(["--fast-llm-name", fast_llm_name])
        plan.append(
            {
                "task": task,
                "phase": "runner",
                "command": runner,
                "stdout_log": str(task_log_dir / "log"),
            }
        )
        plan.append(
            {
                "task": task,
                "phase": "eval",
                "command": [
                    python_bin,
                    "-m",
                    "MLAgentBench.eval",
                    "--log-folder",
                    str(task_log_dir),
                    "--task",
                    task,
                    "--output-file",
                    str(eval_file),
                ],
                "output_file": str(eval_file),
            }
        )
    return plan


def write_command_plan(plan: List[Dict[str, Any]], out_path: Path) -> Dict[str, Any]:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    script_path = out_path.with_suffix(".sh")
    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    for step in plan:
        stdout_log = step.get("stdout_log")
        if stdout_log:
            lines.append(f"mkdir -p {shlex.quote(str(Path(stdout_log).parent))}")
            lines.append(f"{shlex.join([str(item) for item in step['command']])} > {shlex.quote(stdout_log)} 2>&1")
        else:
            output_file = step.get("output_file")
            if output_file:
                lines.append(f"mkdir -p {shlex.quote(str(Path(output_file).parent))}")
            lines.append(shlex.join([str(item) for item in step["command"]]))
        lines.append("")
    script_path.write_text("\n".join(lines), encoding="utf-8")
    script_path.chmod(0o755)
    return {"plan_path": str(out_path), "script_path": str(script_path), "n_steps": len(plan)}


def run_mlagentbench_plan(
    plan: List[Dict[str, Any]],
    *,
    cwd: Optional[Path] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    summary = {
        "cwd": str(cwd) if cwd else None,
        "dry_run": dry_run,
        "steps": [
            {
                "task": step["task"],
                "phase": step["phase"],
                "command": step["command"],
                "shell_command": shlex.join([str(item) for item in step["command"]]),
                **({"stdout_log": step["stdout_log"]} if step.get("stdout_log") else {}),
                **({"output_file": step["output_file"]} if step.get("output_file") else {}),
            }
            for step in plan
        ],
    }
    if dry_run:
        return summary

    for step in plan:
        command = [str(item) for item in step["command"]]
        stdout_log = step.get("stdout_log")
        if stdout_log:
            log_path = Path(stdout_log)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("w", encoding="utf-8") as handle:
                completed = subprocess.run(
                    command,
                    cwd=cwd,
                    text=True,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
        else:
            output_file = step.get("output_file")
            if output_file:
                Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            completed = subprocess.run(command, cwd=cwd, text=True, check=False)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, command)
    return summary


def _leaf_answer(run_dir: Path, row: Dict[str, Any], *, preferred_artifact: str) -> str:
    run_path = str(row.get("run_path") or "")
    if not run_path:
        return ""
    leaf_dir = Path(run_dir) / run_path
    artifact = leaf_dir / preferred_artifact
    if artifact.exists():
        return artifact.read_text(encoding="utf-8")
    leaf_output = leaf_dir / "leaf_output.json"
    if not leaf_output.exists():
        return ""
    data = json.loads(leaf_output.read_text(encoding="utf-8"))
    return str(data.get("answer", ""))


def _swebench_instance_id(row: Dict[str, Any]) -> str:
    task_id = str(row.get("task_id", ""))
    benchmark = str(row.get("benchmark", ""))
    prefix = f"{benchmark}-"
    if task_id.startswith(prefix):
        return task_id[len(prefix) :]
    for known in SWE_BENCH_DATASETS:
        known_prefix = f"{known}-"
        if task_id.startswith(known_prefix):
            return task_id[len(known_prefix) :]
    return task_id


def _model_label(row: Dict[str, Any], variant: str) -> str:
    parts = ["veriharness", variant]
    model_name = row.get("model_name") or row.get("model_client")
    if model_name:
        parts.append(str(model_name))
    return "-".join(parts)


def _parse_manifest(answer: str) -> Dict[str, Any]:
    try:
        data = json.loads(answer)
    except json.JSONDecodeError:
        return {"raw_answer": answer}
    if isinstance(data, dict):
        return data
    return {"raw_answer": answer}


def _mlagentbench_task_name(row: Dict[str, Any]) -> str:
    task_id = str(row.get("task_id", ""))
    prefix = "mlagentbench-"
    if task_id.startswith(prefix):
        return task_id[len(prefix) :]
    return task_id
