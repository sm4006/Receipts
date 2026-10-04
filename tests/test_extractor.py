import json
import os
import unittest
from urllib.error import URLError

from receipts.extractor import (
    AIExtractionError,
    DEFAULT_OLLAMA_MODEL,
    LocalAIUnavailableError,
    extraction_prompt,
    extract_claims,
)


DOCUMENTATION = "Our model achieved 91.8% accuracy. Training used 12 epochs."


class MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps({"response": self.payload}).encode("utf-8")


class MockOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return MockResponse(next(self.responses))


def claim(quote="Our model achieved 91.8% accuracy.", **overrides):
    value = {
        "quote": quote,
        "subject": "model",
        "attribute": "accuracy",
        "value": 91.8,
        "unit": "%",
    }
    value.update(overrides)
    return value


class ExtractorTests(unittest.TestCase):
    def test_prompt_requires_evidence_facing_source_attributes(self):
        prompt = extraction_prompt("Precision is 88%. Training time is 12 minutes.")
        self.assertIn("precision stays precision", prompt)
        self.assertIn("recall stays recall", prompt)
        self.assertIn("dataset_rows", prompt)
        self.assertIn("training_time", prompt)
        self.assertIn("invent a semantic mapping", prompt.lower())

    def test_supported_attributes_are_preserved(self):
        documentation = (
            "Precision is 88%. Recall is 84%. "
            "The documented attributes are precision, recall, dataset_rows, and training_time."
        )
        payload = {
            "claims": [
                claim("Precision is 88%.", attribute="precision", value=88),
                claim("Recall is 84%.", attribute="recall", value=84),
                claim(
                    "The documented attributes are precision, recall, dataset_rows, and training_time.",
                    subject="training",
                    attribute="training_time",
                    value=12,
                    unit="minutes",
                ),
            ]
        }
        claims = extract_claims(documentation, opener=MockOpener([json.dumps(payload)]))
        self.assertEqual(
            [item.attribute for item in claims],
            ["precision", "recall", "training_time"],
        )

    def test_unsupported_synonym_is_not_rewritten(self):
        quote = "Training completed in 12 minutes."
        payload = {"claims": [claim(
            quote,
            subject="training",
            attribute="duration",
            value=12,
            unit="minutes",
        )]}
        claims = extract_claims(quote, opener=MockOpener([json.dumps(payload)]))
        self.assertEqual(claims[0].attribute, "duration")

    def test_valid_structured_response(self):
        opener = MockOpener([json.dumps({"claims": [claim()]})])
        claims = extract_claims(DOCUMENTATION, source_file="README.md", opener=opener)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].source_file, "README.md")
        self.assertEqual(claims[0].quote, claim()["quote"])

    def test_safe_json_extraction_from_wrapped_response(self):
        opener = MockOpener(["Here is the JSON:\n" + json.dumps({"claims": [claim()]})])
        claims = extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(opener.requests), 1)

    def test_fenced_json_with_nullable_unit_matches_exact_schema(self):
        payload = {
            "claims": [
                claim(
                    "Training used 12 epochs.",
                    subject="training",
                    attribute="epochs",
                    value=12,
                    unit=None,
                )
            ]
        }
        opener = MockOpener(["```json\n" + json.dumps(payload) + "\n```"])
        claims = extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(claims), 1)
        self.assertIsNone(claims[0].unit)

    def test_invalid_json_retries_once(self):
        opener = MockOpener(["not json", json.dumps({"claims": [claim()]})])
        claims = extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(claims), 1)
        self.assertEqual(len(opener.requests), 2)
        strict_prompt = json.loads(opener.requests[1][0].data.decode("utf-8"))["prompt"]
        self.assertIn("Do not include markdown fences", strict_prompt)

    def test_failure_after_second_invalid_response(self):
        opener = MockOpener(["not json", "still not json"])
        with self.assertRaises(AIExtractionError):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 2)

    def test_missing_required_field_is_rejected(self):
        invalid = claim()
        del invalid["unit"]
        opener = MockOpener([json.dumps({"claims": [invalid]})])
        with self.assertRaises(AIExtractionError):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_fabricated_quote_is_rejected(self):
        payload = json.dumps({"claims": [claim("This sentence is not in the README.")]})
        opener = MockOpener([payload])
        with self.assertRaisesRegex(AIExtractionError, "fabricated quote"):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_unsupported_claim_is_rejected_without_retry(self):
        invalid = claim(value={"not": "a scalar"})
        opener = MockOpener([json.dumps({"claims": [invalid]})])
        with self.assertRaisesRegex(AIExtractionError, "unsupported"):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_valid_quote_is_required_and_preserved(self):
        quote = "Training used 12 epochs."
        payload = json.dumps({"claims": [claim(quote, attribute="epochs", value=12, unit=None)]})
        claims = extract_claims(DOCUMENTATION, opener=MockOpener([payload]))
        self.assertEqual(claims[0].quote, quote)
        self.assertEqual(claims[0].unit, None)

    def test_ollama_unavailable_is_clear(self):
        def unavailable(request, timeout):
            raise URLError("connection refused")

        with self.assertRaisesRegex(LocalAIUnavailableError, "Local AI extraction is unavailable"):
            extract_claims(DOCUMENTATION, opener=unavailable)

    def test_remote_endpoint_is_rejected(self):
        with self.assertRaisesRegex(AIExtractionError, "endpoint must use the local HTTP service"):
            extract_claims(DOCUMENTATION, endpoint="https://example.com")

    def test_configurable_model_is_sent_to_ollama(self):
        opener = MockOpener([json.dumps({"claims": []})])
        extract_claims(DOCUMENTATION, model="local-test-model", opener=opener)
        body = json.loads(opener.requests[0][0].data.decode("utf-8"))
        self.assertEqual(body["model"], "local-test-model")

    def test_environment_model_and_default(self):
        old_value = os.environ.get("RECEIPTS_OLLAMA_MODEL")
        try:
            os.environ["RECEIPTS_OLLAMA_MODEL"] = "environment-model"
            opener = MockOpener([json.dumps({"claims": []})])
            extract_claims(DOCUMENTATION, opener=opener)
            self.assertEqual(json.loads(opener.requests[0][0].data.decode("utf-8"))["model"], "environment-model")
        finally:
            if old_value is None:
                os.environ.pop("RECEIPTS_OLLAMA_MODEL", None)
            else:
                os.environ["RECEIPTS_OLLAMA_MODEL"] = old_value
        self.assertEqual(DEFAULT_OLLAMA_MODEL, "gemma3:4b")

    def test_verdict_field_is_rejected(self):
        invalid = claim()
        invalid["verdict"] = "VERIFIED"
        opener = MockOpener([json.dumps({"claims": [invalid]})])
        with self.assertRaises(AIExtractionError):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 1)

    def test_multiple_claims_are_extracted(self):
        payload = json.dumps({"claims": [claim(), claim("Training used 12 epochs.", attribute="epochs", value=12, unit=None)]})
        claims = extract_claims(DOCUMENTATION, opener=MockOpener([payload]))
        self.assertEqual(len(claims), 2)
        self.assertEqual([item.attribute for item in claims], ["accuracy", "epochs"])


if __name__ == "__main__":
    unittest.main()
