from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from veriharness.core.orchestrator import Orchestrator
from veriharness.core.types import ExperimentConfig


def run_modal_batch(config: ExperimentConfig, raw_config: Dict[str, Any]) -> Path:
    # Prototype fallback: keep local execution authoritative unless Modal credentials and
    # a remote artifact strategy are explicitly added.
    config.backend = "local"
    return Orchestrator(config, raw_config=raw_config).run()
