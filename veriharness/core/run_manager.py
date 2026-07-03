from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import yaml

from veriharness.core.artifact_store import ArtifactStore
from veriharness.core.event_log import EventLog
from veriharness.core.state_store import StateStore
from veriharness.core.types import ExperimentConfig


class RunManager:
    def __init__(self, base_dir: Path = Path("runs")) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(self, config: ExperimentConfig, raw_config: Dict[str, Any]) -> tuple[str, Path, ArtifactStore, EventLog, StateStore]:
        run_id = self._choose_run_id(config.experiment_id)
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        (run_dir / "artifacts").mkdir(exist_ok=True)
        safe_config = json.loads(json.dumps(raw_config, default=str))
        (run_dir / "config.yaml").write_text(yaml.safe_dump(safe_config, sort_keys=False), encoding="utf-8")
        (run_dir / "git_commit.txt").write_text(self._git_commit(), encoding="utf-8")
        (run_dir / "environment.json").write_text(
            json.dumps(self._environment(config), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        self._update_latest(run_dir)
        store = ArtifactStore(run_dir, run_id)
        events = EventLog(run_dir / "events.jsonl", config.experiment_id, run_id)
        state = StateStore(run_dir / "state.json")
        return run_id, run_dir, store, events, state

    def _choose_run_id(self, experiment_id: str) -> str:
        candidate = experiment_id
        if not (self.base_dir / candidate).exists():
            return candidate
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{experiment_id}-{stamp}"

    def _update_latest(self, run_dir: Path) -> None:
        latest = self.base_dir / "latest"
        try:
            if latest.is_symlink() or latest.exists():
                if latest.is_dir() and not latest.is_symlink():
                    shutil.rmtree(latest)
                else:
                    latest.unlink()
            latest.symlink_to(run_dir.resolve(), target_is_directory=True)
        except OSError:
            (self.base_dir / "latest.txt").write_text(str(run_dir.resolve()), encoding="utf-8")

    def _git_commit(self) -> str:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
                + "\n"
            )
        except Exception:
            return "unknown\n"

    def _environment(self, config: ExperimentConfig) -> Dict[str, Any]:
        return {
            "python": sys.version,
            "platform": platform.platform(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "model_client_name": config.model.client,
            "model_name": config.model.model_name,
        }
