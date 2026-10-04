import unittest
from collections import Counter
from pathlib import Path

from receipts.models import Claim
from receipts.pipeline import run_pipeline
from receipts.verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


DEMO_PROJECT = Path(__file__).parents[1] / "demo" / "receipts_demo"


class DemoProjectTests(unittest.TestCase):
    def test_demo_has_deterministic_target_distribution(self):
        claims = [
            Claim("The recorded accuracy is 91.8%.", "results", "accuracy", 91.8, "%", "README.md"),
            Claim("The results table records dataset_rows as 10000.", "results table", "dataset_rows", 10000, None, "README.md"),
            Claim("The recorded precision is 88%.", "results", "precision", 88, "%", "README.md"),
            Claim("The recorded recall is 84%.", "results", "recall", 84, "%", "README.md"),
            Claim("The experiment used training_epochs equal to 25.", "experiment", "training_epochs", 25, None, "README.md"),
            Claim("The project does not record deployment_latency_ms.", "project", "deployment_latency_ms", 120, "milliseconds", "README.md"),
            Claim("The project does not record f1_score.", "project", "f1_score", 0.87, None, "README.md"),
        ]

        result = run_pipeline(
            DEMO_PROJECT,
            extractor=lambda documentation, source_file: claims,
        )
        distribution = Counter(item.verdict for item in result.verification_results)
        self.assertEqual(
            distribution,
            Counter({
                VERDICT_VERIFIED: 2,
                VERDICT_CONFLICT: 2,
                VERDICT_AMBIGUOUS: 1,
                VERDICT_UNVERIFIABLE: 2,
            }),
        )
        self.assertEqual(len(result.claims), 7)
        self.assertEqual(result.errors, [])

    def test_demo_scans_all_required_files_without_execution(self):
        result = run_pipeline(DEMO_PROJECT, extractor=lambda documentation, source_file: [])
        self.assertEqual(
            set(result.scan.files),
            {"README.md", "results.csv", "config.json", "analysis.ipynb"},
        )
        self.assertEqual(result.scan.errors, [])


if __name__ == "__main__":
    unittest.main()
