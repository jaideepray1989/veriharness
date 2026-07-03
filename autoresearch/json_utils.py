from __future__ import annotations

import json
from typing import Any


def extract_json_object(text: str) -> Any:
    """Parse JSON, tolerating markdown fences or provider preambles."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty provider response")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        fenced = "\n".join(lines).strip()
        try:
            return json.loads(fenced)
        except json.JSONDecodeError:
            pass

    start_candidates = [idx for idx in [stripped.find("{"), stripped.find("[")] if idx != -1]
    if not start_candidates:
        raise ValueError("provider response did not contain JSON")
    start = min(start_candidates)
    stack = []
    in_string = False
    escaped = False
    for offset, char in enumerate(stripped[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in "{[":
            stack.append("}" if char == "{" else "]")
        elif char in "}]":
            if not stack or stack[-1] != char:
                continue
            stack.pop()
            if not stack:
                return json.loads(stripped[start : offset + 1])
    raise ValueError("provider response contained incomplete JSON")
