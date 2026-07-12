from veriharness.core.artifact_store import ArtifactStore


def test_artifact_write_read_list_hash_uri(tmp_path):
    store = ArtifactStore(tmp_path / "run", "run")
    uri = store.write_text("a/b.txt", "hello")
    assert uri == "artifact://run/a/b.txt"
    assert store.read_text("a/b.txt") == "hello"
    assert "a/b.txt" in store.list_artifacts()
    assert len(store.sha256("a/b.txt")) == 64
    assert store.resolve_uri(uri).name == "b.txt"
