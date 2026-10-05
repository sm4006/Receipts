import tempfile
import unittest
import json
from pathlib import Path
from urllib.error import URLError

from receipts.extractor import AIExtractionError, extract_claims
from receipts.models import Claim, VerificationResult
from receipts.pipeline import run_pipeline
from receipts.verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


README = (
    "Our model achieved 91.8% accuracy. "
    "The recorded accuracy was 94.2%. "
    "Training used 12 epochs. "
    "The dataset has 100 rows."
)


def make_claim(quote, attribute, value, unit="%"):
    return Claim(quote, "model", attribute, value, unit, "README.md")


class PipelineTests(unittest.TestCase):
    def project(self, files):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return directory, root

    def test_verified_claim(self):
        directory, root = self.project({"README.md": README, "metrics.csv": "accuracy\n91.8\n"})
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [
                make_claim("Our model achieved 91.8% accuracy.", "accuracy", 91.8)
            ])
            self.assertEqual(result.verification_results[0].verdict, VERDICT_VERIFIED)
        finally:
            directory.cleanup()

    def test_conflict_claim(self):
        directory, root = self.project({"README.md": README, "metrics.csv": "accuracy\n91.8\n"})
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [
                make_claim("The recorded accuracy was 94.2%.", "accuracy", 94.2)
            ])
            self.assertEqual(result.verification_results[0].verdict, VERDICT_CONFLICT)
        finally:
            directory.cleanup()

    def test_ambiguous_claim(self):
        directory, root = self.project({
            "README.md": README,
            "a.csv": "accuracy\n91.8\n",
            "b.csv": "acc\n91.8\n",
        })
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [
                make_claim("Our model achieved 91.8% accuracy.", "accuracy", 91.8)
            ])
            self.assertEqual(result.verification_results[0].verdict, VERDICT_AMBIGUOUS)
        finally:
            directory.cleanup()

    def test_unverifiable_claim(self):
        directory, root = self.project({"README.md": README, "metrics.csv": "accuracy\n91.8\n"})
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [
                make_claim("Training used 12 epochs.", "epochs", 12, None)
            ])
            self.assertEqual(result.verification_results[0].verdict, VERDICT_UNVERIFIABLE)
        finally:
            directory.cleanup()

    def test_multiple_claims_and_provenance(self):
        directory, root = self.project({"README.md": README, "metrics.csv": "accuracy,epochs\n91.8,12\n"})
        try:
            def extractor(text, source_file):
                return [
                    make_claim("Our model achieved 91.8% accuracy.", "accuracy", 91.8),
                    make_claim("Training used 12 epochs.", "epochs", 12, None),
                ]

            result = run_pipeline(root, extractor=extractor)
            self.assertEqual(len(result.claims), 2)
            self.assertEqual(result.claims[0].source_file, "README.md")
            self.assertEqual(result.verification_results[0].claim.quote, result.claims[0].quote)
            self.assertEqual(result.verification_results[0].evidence.source_file, "metrics.csv")
        finally:
            directory.cleanup()

    def test_scanner_errors_are_preserved(self):
        directory, root = self.project({"README.md": README, "bad.json": "{"})
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [])
            self.assertTrue(any("bad.json" in error for error in result.errors))
            self.assertTrue(any("bad.json" in error for error in result.scan.errors))
        finally:
            directory.cleanup()

    def test_ai_errors_are_preserved(self):
        directory, root = self.project({"README.md": README})
        try:
            def extractor(text, source_file):
                raise AIExtractionError("invalid claims")

            result = run_pipeline(root, extractor=extractor)
            self.assertTrue(any("AI extraction failed" in error for error in result.errors))
            self.assertEqual(result.verification_results, [])
        finally:
            directory.cleanup()

    def test_empty_claims_are_supported(self):
        directory, root = self.project({"README.md": README})
        try:
            result = run_pipeline(root, extractor=lambda text, source_file: [])
            self.assertEqual(result.claims, [])
            self.assertEqual(result.verification_results, [])
            self.assertEqual(result.errors, [])
        finally:
            directory.cleanup()

    def test_invalid_project_path_is_preserved(self):
        result = run_pipeline(Path(tempfile.gettempdir()) / "receipts-path-does-not-exist")
        self.assertTrue(result.errors)
        self.assertEqual(result.claims, [])
        self.assertEqual(result.verification_results, [])

    def test_verifier_remains_final_verdict_authority(self):
        directory, root = self.project({"README.md": README, "metrics.csv": "accuracy\n91.8\n"})
        try:
            def extractor(text, source_file):
                return [make_claim("Our model achieved 91.8% accuracy.", "accuracy", 91.8)]

            def verifier(claim, evidence):
                return VerificationResult(claim, evidence[1], VERDICT_CONFLICT, "test verifier result")

            result = run_pipeline(root, extractor=extractor, verifier=verifier)
            self.assertEqual(result.verification_results[0].verdict, VERDICT_CONFLICT)
        finally:
            directory.cleanup()

    def test_unexpected_verifier_errors_are_not_swallowed(self):
        directory, root = self.project({"README.md": README})
        try:
            def extractor(text, source_file):
                return [make_claim("Our model achieved 91.8% accuracy.", "accuracy", 91.8)]

            def verifier(claim, evidence):
                raise RuntimeError("verifier failure")

            with self.assertRaisesRegex(RuntimeError, "verifier failure"):
                run_pipeline(root, extractor=extractor, verifier=verifier)
        finally:
            directory.cleanup()

    def ollama_extractor(self, payload, opener):
        response = json.dumps(payload)

        def extractor(text, source_file):
            return extract_claims(
                text,
                source_file=source_file,
                opener=opener(response),
            )

        return extractor

    def test_real_extractor_and_pipeline_produce_verified_result(self):
        quote = "Our model achieved 91.8% accuracy."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            payload = {"claims": [{
                "quote": quote,
                "subject": "model",
                "attribute": "accuracy",
                "value": 91.8,
                "unit": "%",
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(payload, lambda _: Opener()))
            self.assertEqual(result.verification_results[0].verdict, VERDICT_VERIFIED)
        finally:
            directory.cleanup()

    def test_real_extractor_and_pipeline_produce_conflict_result(self):
        quote = "Our model achieved 94.2% accuracy."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            payload = {"claims": [{
                "quote": quote,
                "subject": "model",
                "attribute": "accuracy",
                "value": 94.2,
                "unit": "%",
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(payload, lambda _: Opener()))
            self.assertEqual(result.verification_results[0].verdict, VERDICT_CONFLICT)
        finally:
            directory.cleanup()

    def test_real_extractor_and_pipeline_produce_ambiguous_result(self):
        quote = "Our model achieved 91.8% accuracy."
        directory, root = self.project({
            "README.md": quote,
            "a.csv": "accuracy\n91.8\n",
            "b.csv": "acc\n91.8\n",
        })
        try:
            payload = {"claims": [{
                "quote": quote,
                "subject": "model",
                "attribute": "accuracy",
                "value": 91.8,
                "unit": "%",
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(payload, lambda _: Opener()))
            self.assertEqual(result.verification_results[0].verdict, VERDICT_AMBIGUOUS)
        finally:
            directory.cleanup()

    def test_real_extractor_and_pipeline_produce_unverifiable_result(self):
        quote = "The project used a private test protocol."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            payload = {"claims": [{
                "quote": quote,
                "subject": "project",
                "attribute": "test protocol",
                "value": "private",
                "unit": None,
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(payload, lambda _: Opener()))
            self.assertEqual(result.verification_results, [])
        finally:
            directory.cleanup()

    def test_real_extractor_preserves_claim_and_evidence_provenance(self):
        quote = "Our model achieved 91.8% accuracy."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            payload = {"claims": [{
                "quote": quote,
                "subject": "model",
                "attribute": "accuracy",
                "value": 91.8,
                "unit": "%",
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(payload, lambda _: Opener()))
            verification = result.verification_results[0]
            self.assertEqual(verification.claim.quote, quote)
            self.assertEqual(verification.claim.source_file, "README.md")
            self.assertEqual(verification.evidence.source_file, "metrics.csv")
            self.assertEqual(verification.evidence.location, "row 2, column accuracy")
            self.assertIn("matches the evidence", verification.reason)
        finally:
            directory.cleanup()

    def test_invalid_ai_output_cannot_reach_verifier(self):
        quote = "Our model achieved 91.8% accuracy."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            invalid_payload = {"claims": [{
                "quote": quote,
                "subject": "model",
                "attribute": "accuracy",
                "value": 91.8,
                "unit": "%",
                "verdict": "VERIFIED",
            }]}

            class Opener:
                def __call__(self, request, timeout):
                    return MockResponse(json.dumps(invalid_payload))

            result = run_pipeline(root, extractor=self.ollama_extractor(invalid_payload, lambda _: Opener()))
            self.assertEqual(result.claims, [])
            self.assertEqual(result.verification_results, [])
            self.assertTrue(any("AI extraction failed" in error for error in result.errors))
        finally:
            directory.cleanup()

    def test_ollama_failure_is_preserved_and_does_not_reach_verifier(self):
        quote = "Our model achieved 91.8% accuracy."
        directory, root = self.project({"README.md": quote, "metrics.csv": "accuracy\n91.8\n"})
        try:
            def unavailable(request, timeout):
                raise URLError("connection refused")

            result = run_pipeline(
                root,
                extractor=lambda text, source_file: extract_claims(
                    text,
                    source_file=source_file,
                    opener=unavailable,
                ),
            )
            self.assertEqual(result.claims, [])
            self.assertEqual(result.verification_results, [])
            self.assertIn("Local AI extraction is unavailable", result.errors[0])
        finally:
            directory.cleanup()


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps({"response": self.payload}).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
