from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, List


class ArtifactStore:
    def __init__(self, run_dir: Path, run_id: str) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

    def path(self, relative_path: str) -> Path:
        clean = relative_path.strip("/")
        return self.run_dir / clean

    def write_text(self, relative_path: str, text: str) -> str:
        path = self.path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return self.uri(relative_path)

    def write_json(self, relative_path: str, payload: Any) -> str:
        return self.write_text(
            relative_path,
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        )

    def read_text(self, relative_path: str) -> str:
        return self.path(relative_path).read_text(encoding="utf-8")

    def read_json(self, relative_path: str) -> Any:
        return json.loads(self.read_text(relative_path))

    def list_artifacts(self, prefix: str = "") -> List[str]:
        root = self.path(prefix) if prefix else self.run_dir
        if not root.exists():
            return []
        files = [path for path in root.rglob("*") if path.is_file()]
        return sorted(str(path.relative_to(self.run_dir)) for path in files)

    def sha256(self, relative_path: str) -> str:
        digest = hashlib.sha256()
        with self.path(relative_path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def uri(self, relative_path: str) -> str:
        return f"artifact://{self.run_id}/{relative_path.strip('/')}"

    def resolve_uri(self, uri: str) -> Path:
        prefix = f"artifact://{self.run_id}/"
        if not uri.startswith(prefix):
            raise ValueError(f"artifact URI does not belong to run {self.run_id}: {uri}")
        return self.path(uri[len(prefix) :])
