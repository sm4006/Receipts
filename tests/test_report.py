import tempfile
import unittest
from pathlib import Path

from receipts.models import Claim, Evidence, VerificationResult
from receipts.pipeline import PipelineResult
from receipts.report import render_report, write_report
from receipts.scanner import ScanResult
from receipts.verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


def verification(verdict, quote):
    claim = Claim(quote, "model", "accuracy", 91.8, "%", "README<&.md")
    evidence = Evidence("metrics<&.csv", "row <2>", "accuracy", "<91.8>", "%", raw_value="<91.8>")
    return VerificationResult(
        claim,
        evidence if verdict != VERDICT_UNVERIFIABLE else None,
        verdict,
        "Reason with <script>alert('x')</script>",
        "91.8<&",
        "91.8>",
    )


class ReportTests(unittest.TestCase):
    def pipeline_result(self, results):
        return PipelineResult(
            scan=ScanResult(),
            claims=[item.claim for item in results],
            verification_results=results,
        )

    def test_report_generation_writes_self_contained_html(self):
        result = self.pipeline_result([verification(VERDICT_VERIFIED, "Claim")])
        with tempfile.TemporaryDirectory() as directory:
            destination = write_report(result, "C:\\projects\\sample<&", Path(directory) / "report.html")
            self.assertTrue(destination.exists())
            content = destination.read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", content)
            self.assertIn("Receipts Verification Report", content)
            self.assertNotIn("<script>alert", content)

    def test_all_verdicts_and_provenance_are_rendered(self):
        results = [
            verification(VERDICT_VERIFIED, "verified"),
            verification(VERDICT_CONFLICT, "conflict"),
            verification(VERDICT_AMBIGUOUS, "ambiguous"),
            verification(VERDICT_UNVERIFIABLE, "unverifiable"),
        ]
        content = render_report(self.pipeline_result(results), "/project")
        for verdict in (VERDICT_VERIFIED, VERDICT_CONFLICT, VERDICT_AMBIGUOUS, VERDICT_UNVERIFIABLE):
            self.assertIn(f">{verdict}<", content)
        self.assertIn("README&lt;&amp;.md", content)
        self.assertIn("metrics&lt;&amp;.csv", content)
        self.assertIn("91.8&lt;&amp;", content)
        self.assertIn("91.8&gt;", content)
        self.assertIn("Reason with &lt;script&gt;", content)

    def test_summary_counts_and_exact_quote_are_rendered(self):
        results = [
            verification(VERDICT_VERIFIED, "verified quote"),
            verification(VERDICT_VERIFIED, "second verified quote"),
            verification(VERDICT_CONFLICT, "conflicting quote"),
            verification(VERDICT_AMBIGUOUS, "ambiguous quote"),
            verification(VERDICT_UNVERIFIABLE, "unverifiable quote"),
        ]
        content = render_report(self.pipeline_result(results), "/project")
        self.assertIn("Claims<strong>5</strong>", content)
        self.assertIn("VERIFIED<strong>2</strong>", content)
        self.assertIn("CONFLICT<strong>1</strong>", content)
        self.assertIn("AMBIGUOUS<strong>1</strong>", content)
        self.assertIn("UNVERIFIABLE<strong>1</strong>", content)
        self.assertIn("verified quote", content)
        self.assertIn("metrics&lt;&amp;.csv (row &lt;2&gt;)", content)

    def test_empty_results_are_reported(self):
        content = render_report(self.pipeline_result([]), "/empty")
        self.assertIn("Claims<strong>0</strong>", content)
        self.assertIn("No verification results.", content)

    def test_special_characters_are_escaped(self):
        content = render_report(
            self.pipeline_result([verification(VERDICT_VERIFIED, '"<b>unsafe</b>&"')]),
            "/project<&",
        )
        self.assertIn("&quot;&lt;b&gt;unsafe&lt;/b&gt;&amp;&quot;", content)
        self.assertNotIn("<b>unsafe</b>", content)
        self.assertNotIn("<script>", content)

    def test_rendering_is_deterministic(self):
        result = self.pipeline_result([verification(VERDICT_CONFLICT, "same")])
        self.assertEqual(render_report(result, "/project"), render_report(result, "/project"))


if __name__ == "__main__":
    unittest.main()
