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
from veriharness.experiments.plots import write_plots
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
    concurrency: int = typer.Option(
        1,
        help="Number of task-variants to run in parallel (local backend). "
        "Default 1 = sequential. Use >1 to exploit a batching-capable endpoint "
        "(e.g. an Ollama or vLLM server).",
    ),
) -> None:
    run_dir = run_config(config, backend=backend, concurrency=concurrency)
    console.print(f"Run complete: {run_dir}")


@app.command("resume-run")
def resume_run(
    run_dir: Path = typer.Option(..., help="Existing run directory."),
    concurrency: int = typer.Option(
        1, help="Number of task-variants to run in parallel while resuming. Default 1 = sequential."
    ),
) -> None:
    """Resume an interrupted local run by skipping persisted result rows."""
    run_dir = _resolve_run_dir(run_dir)
    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        raise typer.BadParameter(f"missing run config: {config_path}")
    config, raw = load_config(config_path)
    summary = Orchestrator(config, raw_config=raw, concurrency=concurrency).resume(run_dir)
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
