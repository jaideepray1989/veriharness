from __future__ import annotations

import json
import os
import socket
import urllib.parse
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.console import Console

from veriharness.benchmarks.generators import generate_named_tasks
from veriharness.core.orchestrator import Orchestrator
from veriharness.core.types import ExperimentConfig
from veriharness.experiments.aggregate import read_results, write_aggregate
from veriharness.experiments.official_runners import (
    build_mlagentbench_commands,
    build_swebench_command,
    export_mlagentbench_manifests,
    export_swebench_predictions,
    run_command,
    run_mlagentbench_plan,
    write_command_plan,
)
from veriharness.experiments.plots import write_plots
from veriharness.experiments.replay_repair import ReplayRepairRunner
from veriharness.experiments.runner import load_config, run_config
from veriharness.experiments.workshop_report import compile_workshop_bundle
from veriharness.llm.coreai_client import CoreAIClient

app = typer.Typer(help="VeriHarness experiment CLI.")
console = Console()


def _resolve_run_dir(run_dir: Path) -> Path:
    if run_dir == Path("runs/latest") and not run_dir.exists():
        latest_file = Path("runs/latest.txt")
        if latest_file.exists():
            return Path(latest_file.read_text(encoding="utf-8").strip())
    return run_dir


def _emit_json(payload: object, out: Optional[Path] = None) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    typer.echo(text, nl=False)


@app.command("generate-tasks")
def generate_tasks(
    benchmark: str = typer.Option(..., help="Benchmark name."),
    out: Path = typer.Option(..., help="Output JSONL path."),
    n: int = typer.Option(20, help="Number of tasks."),
    seed: int = typer.Option(1, help="Generation seed."),
) -> None:
    tasks = generate_named_tasks(benchmark, n, seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for task in tasks:
            handle.write(task.model_dump_json() + "\n")
    console.print(f"Wrote {len(tasks)} tasks to {out}")


@app.command("run")
def run(
    config: Path = typer.Option(..., help="Experiment config YAML."),
    backend: str = typer.Option("local", help="Execution backend: local or modal."),
) -> None:
    run_dir = run_config(config, backend=backend)
    console.print(f"Run complete: {run_dir}")


@app.command("run-replay-repair")
def run_replay_repair(
    config: Path = typer.Option(..., help="Experiment config YAML."),
    backend: str = typer.Option("local", help="Execution backend: local only for replay repair."),
) -> None:
    """Run repair-policy variants from identical frozen failed attempts."""
    if backend != "local":
        raise typer.BadParameter("replay repair currently supports only the local backend")
    config_obj, raw = load_config(config)
    config_obj.backend = backend
    run_dir = ReplayRepairRunner(config_obj, raw_config=raw).run()
    console.print(f"Replay repair run complete: {run_dir}")


@app.command("resume-run")
def resume_run(run_dir: Path = typer.Option(..., help="Existing run directory.")) -> None:
    """Resume an interrupted local run by skipping persisted result rows."""
    run_dir = _resolve_run_dir(run_dir)
    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        raise typer.BadParameter(f"missing run config: {config_path}")
    config, raw = load_config(config_path)
    summary = Orchestrator(config, raw_config=raw).resume(run_dir)
    console.print(json.dumps(summary, indent=2, sort_keys=True))


@app.command("run-model-matrix")
def run_model_matrix(
    config: Path = typer.Option(..., help="Base experiment config YAML."),
    models_config: Path = typer.Option(Path("configs/models.yaml"), help="Model catalog YAML."),
    models: Optional[str] = typer.Option(None, help="Comma-separated model keys. Defaults to all catalog entries."),
    backend: str = typer.Option("local", help="Execution backend: local or modal."),
    skip_unavailable: bool = typer.Option(True, help="Skip models that are missing local services or credentials."),
) -> None:
    """Run the same experiment config across multiple model catalog entries."""
    base_config, base_raw = load_config(config)
    catalog_raw = yaml.safe_load(models_config.read_text(encoding="utf-8")) or {}
    catalog = catalog_raw.get("models", {})
    selected = [item.strip() for item in models.split(",")] if models else list(catalog)
    run_dirs = []
    skipped = []

    for key in selected:
        if key not in catalog:
            skipped.append({"model": key, "reason": "not in model catalog"})
            continue
        model_spec = dict(catalog[key])
        if skip_unavailable and _model_unavailable(model_spec):
            skipped.append({"model": key, "reason": "unavailable or unconfigured"})
            continue

        raw = json.loads(json.dumps(base_raw, default=str))
        raw["experiment_id"] = f"{base_config.experiment_id}_{key}"
        raw["model"] = model_spec
        matrix_config = ExperimentConfig.model_validate(raw)
        matrix_config.backend = backend
        try:
            run_dir = Orchestrator(matrix_config, raw_config=raw).run()
            run_dirs.append({"model": key, "run_dir": str(run_dir)})
            console.print(f"{key}: {run_dir}")
        except Exception as exc:
            if not skip_unavailable:
                raise
            skipped.append({"model": key, "reason": str(exc)})

    console.print(json.dumps({"runs": run_dirs, "skipped": skipped}, indent=2, sort_keys=True))


@app.command("aggregate")
def aggregate(run_dir: Path = typer.Option(..., help="Run directory.")) -> None:
    run_dir = _resolve_run_dir(run_dir)
    aggregate_data = write_aggregate(run_dir)
    console.print(json.dumps(aggregate_data, indent=2, sort_keys=True))


@app.command("export-swebench-predictions")
def export_swebench_predictions_cmd(
    run_dir: Path = typer.Option(..., help="VeriHarness run directory."),
    out: Path = typer.Option(..., help="Official SWE-bench predictions JSONL path."),
    variant: str = typer.Option(..., help="Variant to export, e.g. H4."),
    benchmark: str = typer.Option("swebench_lite", help="swebench_lite or swebench_verified."),
    model_name: Optional[str] = typer.Option(None, help="Override model_name_or_path in predictions."),
    include_empty: bool = typer.Option(True, "--include-empty/--drop-empty", help="Include empty patches as unresolved predictions."),
    only_success: bool = typer.Option(False, help="Export only rows marked successful by VeriHarness local gates."),
    summary_out: Optional[Path] = typer.Option(None, help="Optional path for machine-readable export summary."),
) -> None:
    """Export VeriHarness SWE-bench patch artifacts to official prediction JSONL."""
    run_dir = _resolve_run_dir(run_dir)
    summary = export_swebench_predictions(
        run_dir,
        out,
        variant=variant,
        benchmark=benchmark,
        model_name=model_name,
        include_empty=include_empty,
        only_success=only_success,
    )
    _emit_json(summary, summary_out)


@app.command("run-swebench-official")
def run_swebench_official_cmd(
    predictions_path: Path = typer.Option(..., help="Official SWE-bench predictions JSONL."),
    dataset_name: str = typer.Option("princeton-nlp/SWE-bench_Lite", help="Official SWE-bench dataset name."),
    run_id: str = typer.Option(..., help="Official SWE-bench run id."),
    python_bin: str = typer.Option(".venv/bin/python", help="Python executable with swebench installed."),
    max_workers: int = typer.Option(4, help="SWE-bench max_workers."),
    timeout: int = typer.Option(1800, help="Per-instance timeout in seconds."),
    cache_level: str = typer.Option("env", help="SWE-bench cache level."),
    report_dir: Optional[Path] = typer.Option(None, help="Optional SWE-bench report directory."),
    instance_ids: Optional[str] = typer.Option(None, help="Optional comma-separated instance IDs."),
    modal: bool = typer.Option(False, help="Run via SWE-bench Modal support."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Print command without executing by default."),
    summary_out: Optional[Path] = typer.Option(None, help="Optional path for machine-readable command summary."),
) -> None:
    """Run or print the official SWE-bench evaluator command."""
    ids = [item.strip() for item in instance_ids.split(",")] if instance_ids else None
    command = build_swebench_command(
        predictions_path,
        dataset_name=dataset_name,
        run_id=run_id,
        python_bin=python_bin,
        max_workers=max_workers,
        timeout=timeout,
        cache_level=cache_level,
        report_dir=report_dir,
        instance_ids=ids,
        modal=modal,
    )
    summary = run_command(command, dry_run=dry_run)
    _emit_json(summary, summary_out)


@app.command("export-mlagentbench-manifests")
def export_mlagentbench_manifests_cmd(
    run_dir: Path = typer.Option(..., help="VeriHarness run directory."),
    out_dir: Path = typer.Option(..., help="Directory for exported MLAgentBench manifests."),
    variant: str = typer.Option(..., help="Variant to export, e.g. H4."),
    include_unsuccessful: bool = typer.Option(False, help="Include rows that failed local manifest gates."),
    summary_out: Optional[Path] = typer.Option(None, help="Optional path for machine-readable export summary."),
) -> None:
    """Export VeriHarness MLAgentBench research plans from leaf artifacts."""
    run_dir = _resolve_run_dir(run_dir)
    summary = export_mlagentbench_manifests(
        run_dir,
        out_dir,
        variant=variant,
        include_unsuccessful=include_unsuccessful,
    )
    _emit_json(summary, summary_out)


@app.command("run-mlagentbench-official")
def run_mlagentbench_official_cmd(
    tasks: str = typer.Option(..., help="Comma-separated MLAgentBench task names."),
    python_bin: str = typer.Option(".venv/bin/python", help="Python executable with MLAgentBench installed."),
    task_python: str = typer.Option(".venv/bin/python", help="Python executable passed to MLAgentBench tasks."),
    log_root: Path = typer.Option(Path("official_runs/mlagentbench/logs"), help="MLAgentBench log root."),
    work_root: Path = typer.Option(Path("official_runs/mlagentbench/workspace"), help="MLAgentBench work root."),
    eval_root: Path = typer.Option(Path("official_runs/mlagentbench/eval"), help="MLAgentBench eval output root."),
    out_plan: Optional[Path] = typer.Option(None, help="Optional JSON command plan path; a .sh script is also written."),
    cwd: Optional[Path] = typer.Option(None, help="MLAgentBench repo root or execution directory."),
    device: str = typer.Option("0", help="MLAgentBench device argument."),
    agent_type: Optional[str] = typer.Option("Agent", help="MLAgentBench agent_type; use empty string to omit."),
    llm_name: Optional[str] = typer.Option(None, help="Optional --llm-name."),
    edit_script_llm_name: Optional[str] = typer.Option(None, help="Optional --edit-script-llm-name."),
    fast_llm_name: Optional[str] = typer.Option(None, help="Optional --fast-llm-name."),
    prepare: bool = typer.Option(True, "--prepare/--no-prepare", help="Include prepare_task step."),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Print command plan without executing by default."),
    summary_out: Optional[Path] = typer.Option(None, help="Optional path for machine-readable command summary."),
) -> None:
    """Run or print official MLAgentBench prepare/runner/eval commands."""
    task_names = [item.strip() for item in tasks.split(",") if item.strip()]
    plan = build_mlagentbench_commands(
        task_names,
        python_bin=python_bin,
        task_python=task_python,
        log_root=log_root,
        work_root=work_root,
        eval_root=eval_root,
        device=device,
        agent_type=agent_type or None,
        llm_name=llm_name,
        edit_script_llm_name=edit_script_llm_name,
        fast_llm_name=fast_llm_name,
        prepare=prepare,
    )
    summary = run_mlagentbench_plan(plan, cwd=cwd, dry_run=dry_run)
    if out_plan is not None:
        summary["written_plan"] = write_command_plan(plan, out_plan)
    _emit_json(summary, summary_out)


@app.command("compile-workshop")
def compile_workshop(
    run_dirs: str = typer.Option(..., help="Comma-separated run directories."),
    out_dir: Path = typer.Option(Path("runs/workshop_compiled"), help="Output directory."),
    expected_rows: int = typer.Option(0, help="Expected rows per complete model run."),
) -> None:
    """Compile model-matrix runs into workshop-ready tables and examples."""
    paths = [_resolve_run_dir(Path(item.strip())) for item in run_dirs.split(",") if item.strip()]
    summary = compile_workshop_bundle(paths, out_dir=out_dir, expected_rows=expected_rows)
    console.print(json.dumps(summary, indent=2, sort_keys=True))


@app.command("plot")
def plot(run_dir: Path = typer.Option(..., help="Run directory.")) -> None:
    run_dir = _resolve_run_dir(run_dir)
    paths = write_plots(run_dir)
    for path in paths:
        console.print(path)


@app.command("inspect-run")
def inspect_run(run_dir: Path = typer.Option(..., help="Run directory.")) -> None:
    run_dir = _resolve_run_dir(run_dir)
    rows = read_results(run_dir)
    variants = sorted({row["variant"] for row in rows})
    console.print(f"Run: {run_dir}")
    console.print(f"Rows: {len(rows)}")
    console.print(f"Tasks: {len({row['task_id'] for row in rows})}")
    console.print(f"Variants: {', '.join(variants)}")
    for variant in variants:
        group = [row for row in rows if row["variant"] == variant]
        success = sum(1 for row in group if row.get("success")) / len(group) if group else 0
        premature = sum(1 for row in group if row.get("premature_stop")) / len(group) if group else 0
        console.print(f"{variant}: success={success:.3f} premature_stop={premature:.3f}")
    failure_counts = {}
    for row in rows:
        for reason in row.get("failure_reasons", []):
            failure_counts[reason] = failure_counts.get(reason, 0) + 1
    console.print(f"Top failures: {dict(sorted(failure_counts.items(), key=lambda item: -item[1])[:8])}")
    console.print(f"Artifacts: {run_dir / 'artifacts'}")


@app.command("print-status")
def print_status(run_dir: Optional[Path] = typer.Option(None, help="Run directory.")) -> None:
    target = _resolve_run_dir(run_dir or Path("runs/latest"))
    if not target.exists():
        console.print("No run found.")
        return
    inspect_run(target)


@app.command("check-coreai")
def check_coreai() -> None:
    """Check local Apple FoundationModels/CoreAI availability."""
    client = CoreAIClient()
    status = client.availability()
    console.print(json.dumps(status, indent=2, sort_keys=True))


def _model_unavailable(model_spec: dict) -> bool:
    client = model_spec.get("client")
    if client == "openai" and not os.environ.get("OPENAI_API_KEY"):
        return True
    if client == "local":
        endpoint = str(model_spec.get("endpoint", "http://localhost:11434/v1/chat/completions"))
        return not _local_endpoint_available(endpoint)
    return False


def _local_endpoint_available(endpoint: str) -> bool:
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = parsed.hostname
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


if __name__ == "__main__":
    app()
