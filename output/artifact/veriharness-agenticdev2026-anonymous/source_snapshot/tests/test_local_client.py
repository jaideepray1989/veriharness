import json

from veriharness.core.types import ContextPack, LeafRequest, TaskSpec
from veriharness.llm.local_client import LocalClient


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        output = {
            "task_id": "seed-task",
            "answer": "ok",
            "artifacts": [],
            "claims": [],
            "self_assessment": {},
            "done": True,
        }
        return json.dumps({"choices": [{"message": {"content": json.dumps(output)}}]}).encode()


def test_local_client_sends_sampling_seed(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    task = TaskSpec(task_id="seed-task", family="test", description="Return ok")
    pack = ContextPack(task_id=task.task_id, variant="test", objective="Return ok")
    request = LeafRequest(context_pack=pack, task=task)
    client = LocalClient(model="test-model", temperature=0.3, top_p=0.9, seed=1729, timeout_seconds=9)

    output = json.loads(client.generate(request))

    assert output["answer"] == "ok"
    assert captured["payload"]["seed"] == 1729
    assert captured["payload"]["temperature"] == 0.3
    assert captured["payload"]["top_p"] == 0.9
    assert captured["timeout"] == 9
