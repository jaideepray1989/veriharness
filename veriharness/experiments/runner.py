from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from veriharness.core.orchestrator import Orchestrator
from veriharness.core.types import ExperimentConfig


def load_config(path: Path) -> tuple[ExperimentConfig, Dict[str, Any]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    config = ExperimentConfig.model_validate(raw)
    return config, raw


def run_config(path: Path, backend: str = "local") -> Path:
    config, raw = load_config(path)
    config.backend = backend
    if backend == "modal":
        from veriharness.modal.modal_batch import run_modal_batch

        return run_modal_batch(config, raw)
    return Orchestrator(config, raw_config=raw).run()
