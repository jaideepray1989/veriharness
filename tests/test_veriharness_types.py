from veriharness.core.types import Claim, EvidenceRef, GateResult, LeafOutput, TaskSpec


def test_data_model_round_trip():
    task = TaskSpec(
        task_id="t1",
        family="context_trace",
        description="desc",
        input_payload={"x": 1},
        hidden_oracle_payload={"oracle_type": "context_trace"},
        acceptance_criteria=["ok"],
        metadata={"seed": 1},
    )
    restored = TaskSpec.model_validate_json(task.model_dump_json())
    assert restored == task

    output = LeafOutput(
        task_id="t1",
        answer='{"export_format": "jsonl", "fields": ["id", "value"]}',
        artifacts=["answer.json"],
        claims=[Claim(claim="format jsonl", evidence_refs=[EvidenceRef(source="task")])],
        done=True,
    )
    assert LeafOutput.model_validate_json(output.model_dump_json()) == output
    assert GateResult(gate_name="schema", passed=True).model_dump()["passed"] is True
