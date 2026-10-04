import io
import tempfile
import unittest
from pathlib import Path

from receipts.cli import main
from receipts.models import Claim, Evidence, VerificationResult
from receipts.scanner import ScanResult
from receipts.pipeline import PipelineResult
from receipts.verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


def result(verdict, quote):
    claim = Claim(quote, "model", "accuracy", 91.8, "%", "README.md")
    evidence = Evidence("metrics.csv", "row 2, column accuracy", "accuracy", "91.8", "%")
    return VerificationResult(claim, evidence, verdict, "deterministic test reason")


class CLITests(unittest.TestCase):
    def run_cli(self, path, pipeline_result=None):
        output = io.StringIO()
        errors = io.StringIO()
        pipeline = (lambda project_path: pipeline_result)
        code = main([str(path)], pipeline=pipeline, output=output, errors=errors)
        return code, output.getvalue(), errors.getvalue()

    def test_missing_path_is_rejected(self):
        output = io.StringIO()
        errors = io.StringIO()
        code = main([], output=output, errors=errors)
        self.assertNotEqual(code, 0)
        self.assertIn("required", errors.getvalue())

    def test_nonexistent_path_is_rejected(self):
        output = io.StringIO()
        errors = io.StringIO()
        path = Path(tempfile.gettempdir()) / "receipts-cli-does-not-exist"
        code = main([str(path)], output=output, errors=errors)
        self.assertEqual(code, 2)
        self.assertIn("does not exist", errors.getvalue())

    def test_non_directory_path_is_rejected(self):
        with tempfile.NamedTemporaryFile() as file:
            output = io.StringIO()
            errors = io.StringIO()
            code = main([file.name], output=output, errors=errors)
            self.assertEqual(code, 2)
            self.assertIn("not a directory", errors.getvalue())

    def test_successful_pipeline_execution_and_provenance_output(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline_result = PipelineResult(
                scan=ScanResult(),
                claims=[result(VERDICT_VERIFIED, "The model achieved 91.8%.").claim],
                verification_results=[result(VERDICT_VERIFIED, "The model achieved 91.8%.")],
            )
            code, output, errors = self.run_cli(directory, pipeline_result)
            self.assertEqual(code, 0)
            self.assertEqual(errors, "")
            self.assertIn("VERDICT: VERIFIED", output)
            self.assertIn("CLAIM: The model achieved 91.8%.", output)
            self.assertIn("SOURCE: README.md", output)
            self.assertIn("EVIDENCE: metrics.csv", output)
            self.assertIn("REASON: deterministic test reason", output)

    def test_successful_run_generates_report(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline_result = PipelineResult(scan=ScanResult())
            report_calls = []

            def report_writer(result, project_path, output_path):
                report_calls.append((result, project_path, output_path))
                return Path(output_path)

            output = io.StringIO()
            errors = io.StringIO()
            code = main(
                [directory],
                pipeline=lambda project_path: pipeline_result,
                report_writer=report_writer,
                output=output,
                errors=errors,
            )

            self.assertEqual(code, 0)
            self.assertEqual(errors.getvalue(), "")
            self.assertEqual(len(report_calls), 1)
            self.assertEqual(report_calls[0][1], Path(directory))
            self.assertEqual(report_calls[0][2], "report.html")
            self.assertIn("Report: report.html", output.getvalue())

    def test_multiple_verdicts_and_summary_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            verification_results = [
                result(VERDICT_VERIFIED, "verified"),
                result(VERDICT_CONFLICT, "conflict"),
                result(VERDICT_AMBIGUOUS, "ambiguous"),
                result(VERDICT_UNVERIFIABLE, "unverifiable"),
                result(VERDICT_VERIFIED, "verified again"),
            ]
            pipeline_result = PipelineResult(
                scan=ScanResult(),
                claims=[item.claim for item in verification_results],
                verification_results=verification_results,
            )
            code, output, _ = self.run_cli(directory, pipeline_result)
            self.assertEqual(code, 0)
            self.assertIn("Claims:       5", output)
            self.assertIn("VERIFIED:     2", output)
            self.assertIn("CONFLICT:     1", output)
            self.assertIn("AMBIGUOUS:    1", output)
            self.assertIn("UNVERIFIABLE: 1", output)

    def test_pipeline_errors_are_printed_and_return_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline_result = PipelineResult(
                scan=ScanResult(),
                errors=["AI extraction failed for README.md: local service unavailable"],
            )
            code, output, errors = self.run_cli(directory, pipeline_result)
            self.assertEqual(code, 1)
            self.assertIn("ERRORS:", output)
            self.assertIn("local service unavailable", output)
            self.assertEqual(errors, "")

    def test_valid_empty_project_reports_zero_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            pipeline_result = PipelineResult(scan=ScanResult())
            code, output, errors = self.run_cli(directory, pipeline_result)
            self.assertEqual(code, 0)
            self.assertEqual(errors, "")
            self.assertIn("Claims:       0", output)
            self.assertIn("VERIFIED:     0", output)
            self.assertIn("CONFLICT:     0", output)
            self.assertIn("AMBIGUOUS:    0", output)
            self.assertIn("UNVERIFIABLE: 0", output)

    def test_cli_does_not_alter_verifier_verdicts(self):
        with tempfile.TemporaryDirectory() as directory:
            verification_results = [
                result(VERDICT_CONFLICT, "claim"),
                result(VERDICT_UNVERIFIABLE, "claim without evidence"),
            ]
            pipeline_result = PipelineResult(
                scan=ScanResult(),
                claims=[item.claim for item in verification_results],
                verification_results=verification_results,
            )
            _, output, _ = self.run_cli(directory, pipeline_result)
            self.assertEqual(output.count("VERDICT: CONFLICT"), 1)
            self.assertEqual(output.count("VERDICT: UNVERIFIABLE"), 1)
            self.assertNotIn("VERDICT: VERIFIED\nCLAIM: claim", output)


if __name__ == "__main__":
    unittest.main()
