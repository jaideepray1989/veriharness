from veriharness.core.event_log import EventLog


def test_events_append_correctly(tmp_path):
    log = EventLog(tmp_path / "events.jsonl", "exp", "run")
    log.append("experiment_started", payload={"x": 1})
    log.append("experiment_completed")
    rows = list(log.read())
    assert [row["event_type"] for row in rows] == ["experiment_started", "experiment_completed"]
    assert rows[0]["experiment_id"] == "exp"
