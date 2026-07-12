from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateStore:
    def __init__(self, path: Path) -> None:
        self._lock = threading.RLock()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.state = {
                "tasks": {},
                "accepted_facts": {},
                "rejected_facts": {},
                "open_failures": {},
                "run_metadata": {},
                "leaderboard_rows": [],
            }
            self.save()

    def save(self) -> None:
        with self._lock:
            self.path.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def set_task_status(self, task_id: str, variant: str, status: str) -> None:
        with self._lock:
            self.state["tasks"].setdefault(task_id, {})[variant] = status
            self.save()

    def get_task_status(self, task_id: str, variant: str) -> Optional[str]:
        return self.state["tasks"].get(task_id, {}).get(variant)

    def add_accepted_fact(self, task_id: str, fact: str) -> None:
        with self._lock:
            self.state["accepted_facts"].setdefault(task_id, [])
            if fact not in self.state["accepted_facts"][task_id]:
                self.state["accepted_facts"][task_id].append(fact)
            self.save()

    def add_rejected_fact(self, task_id: str, fact: str) -> None:
        with self._lock:
            self.state["rejected_facts"].setdefault(task_id, [])
            if fact not in self.state["rejected_facts"][task_id]:
                self.state["rejected_facts"][task_id].append(fact)
            self.save()

    def get_accepted_facts(self, task_id: str) -> List[str]:
        return list(self.state["accepted_facts"].get(task_id, []))

    def get_rejected_facts(self, task_id: str) -> List[str]:
        return list(self.state["rejected_facts"].get(task_id, []))

    def set_open_failures(self, task_id: str, variant: str, failures: List[str]) -> None:
        with self._lock:
            self.state["open_failures"].setdefault(task_id, {})[variant] = failures
            self.save()

    def set_run_metadata(self, key: str, value: Dict[str, Any]) -> None:
        with self._lock:
            self.state["run_metadata"][key] = value
            self.save()

    def append_leaderboard_row(self, row: Dict[str, Any]) -> None:
        with self._lock:
            self.state["leaderboard_rows"].append(row)
            self.save()
