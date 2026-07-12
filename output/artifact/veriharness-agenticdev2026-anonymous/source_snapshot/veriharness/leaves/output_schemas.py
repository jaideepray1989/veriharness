from __future__ import annotations

from typing import Any, Dict

from veriharness.core.types import LeafOutput


def leaf_output_schema() -> Dict[str, Any]:
    return LeafOutput.model_json_schema()
