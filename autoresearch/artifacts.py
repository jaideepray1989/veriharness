from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import slugify


def utc_run_id(label: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = slugify(label) if label else "run"
    return f"{stamp}_{suffix}"


@dataclass
class ArtifactStore:
    root: Path
    manifest: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(cls, base_dir: Path, label: str) -> "ArtifactStore":
        root = base_dir / utc_run_id(label)
        root.mkdir(parents=True, exist_ok=False)
        store = cls(root=root)
        store.write_json("manifest.json", {"root": str(root), "artifacts": []}, record=False)
        return store

    def plan_dir(self, plan_id: str) -> Path:
        path = self.root / slugify(plan_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, relative: str, data: Any, record: bool = True) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if record:
            self.record(relative, "json")
        return path

    def write_text(self, relative: str, text: str, kind: str = "text", record: bool = True) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if record:
            self.record(relative, kind)
        return path

    def record(self, relative: str, kind: str, extra: Optional[Dict[str, Any]] = None) -> None:
        item = {
            "path": relative,
            "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra:
            item.update(extra)
        self.manifest.append(item)
        self.flush_manifest()

    def flush_manifest(self) -> None:
        payload = {"root": str(self.root), "artifacts": self.manifest}
        (self.root / "manifest.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
