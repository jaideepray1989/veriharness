import tempfile
import unittest
from pathlib import Path

from autoresearch.harness import AutoResearchHarness, HarnessConfig
from autoresearch.llm import MockProvider
from autoresearch.models import ResearchPlan


class HarnessTests(unittest.TestCase):
    def test_mock_run_writes_report(self):
        plan = ResearchPlan(
            plan_id="smoke",
            title="Smoke Test",
            objective="Verify orchestration.",
            questions=["Does the harness route work?"],
            worker_budget=2,
        )
        with tempfile.TemporaryDirectory() as tmp:
            harness = AutoResearchHarness(
                MockProvider(),
                HarnessConfig(output_dir=Path(tmp), max_tasks=2, concurrency=2),
            )
            store = harness.run([plan], label="test")
            report = store.root / "smoke" / "report.md"
            self.assertTrue(report.exists())
            text = report.read_text(encoding="utf-8")
            self.assertIn("compact JSON artifacts", text)
            self.assertTrue((store.root / "smoke" / "workers" / "methods.json").exists())


if __name__ == "__main__":
    unittest.main()
