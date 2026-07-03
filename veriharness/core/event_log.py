from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

EVENT_TYPES = {
    "experiment_started",
    "task_started",
    "context_pack_created",
    "leaf_started",
    "leaf_completed",
    "gate_started",
    "gate_completed",
    "task_accepted",
    "task_rejected",
    "task_retried",
    "experiment_resumed",
    "experiment_completed",
    "exception",
}


class EventLog:
    def __init__(self, path: Path, experiment_id: str, run_id: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.experiment_id = experiment_id
        self.run_id = run_id

    def append(
        self,
        event_type: str,
        *,
        task_id: Optional[str] = None,
        variant: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError(f"unknown event type: {event_type}")
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "task_id": task_id,
            "variant": variant,
            "event_type": event_type,
            "payload": payload or {},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return row

    def read(self) -> Iterator[Dict[str, Any]]:
        if not self.path.exists():
            return iter(())

        def _iter() -> Iterator[Dict[str, Any]]:
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        yield json.loads(line)

        return _iter()
