from veriharness.core.state_store import StateStore


def test_state_persists_across_restart(tmp_path):
    path = tmp_path / "state.json"
    store = StateStore(path)
    store.set_task_status("t1", "H3", "accepted")
    store.add_accepted_fact("t1", "jsonl")
    restarted = StateStore(path)
    assert restarted.get_task_status("t1", "H3") == "accepted"
    assert restarted.get_accepted_facts("t1") == ["jsonl"]
