from __future__ import annotations

try:
    import modal
except Exception:  # pragma: no cover - optional import path
    modal = None


if modal is not None:
    app = modal.App("veriharness")
else:
    app = None
