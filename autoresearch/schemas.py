PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["research_plan_id", "synthesis_brief", "tasks"],
    "properties": {
        "research_plan_id": {"type": "string"},
        "synthesis_brief": {"type": "string"},
        "tasks": {
            "type": "array",
            "minItems": 1,
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "task_id",
                    "title",
                    "worker_kind",
                    "question",
                    "instructions",
                    "expected_output",
                ],
                "properties": {
                    "task_id": {"type": "string"},
                    "title": {"type": "string"},
                    "worker_kind": {"type": "string"},
                    "question": {"type": "string"},
                    "instructions": {"type": "string"},
                    "expected_output": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


WORKER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "task_id",
        "worker_kind",
        "summary",
        "findings",
        "assumptions",
        "uncertainties",
        "next_questions",
        "confidence",
    ],
    "properties": {
        "task_id": {"type": "string"},
        "worker_kind": {"type": "string"},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim", "rationale", "evidence_hint", "actionability"],
                "properties": {
                    "claim": {"type": "string"},
                    "rationale": {"type": "string"},
                    "evidence_hint": {"type": "string"},
                    "actionability": {"type": "string"},
                },
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "next_questions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


SYNTHESIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "plan_id",
        "executive_summary",
        "answer",
        "findings_by_question",
        "recommendations",
        "conflicts_or_tensions",
        "open_questions",
        "confidence",
    ],
    "properties": {
        "plan_id": {"type": "string"},
        "executive_summary": {"type": "string"},
        "answer": {"type": "string"},
        "findings_by_question": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "answer", "supporting_worker_tasks"],
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                    "supporting_worker_tasks": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "conflicts_or_tensions": {"type": "array", "items": {"type": "string"}},
        "open_questions": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}
