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
    def test_smart_fertilizer_fragments_are_rejected_by_claim_quality_filter(self):
        documentation = (
            "# Project Overview\n\n"
            "Machine Learning (Random Forest)\n"
            "Nitrogen (N)\n"
            "Temperature\n"
            "Pomegranate\n"
            "Urea, DAP, MOP\n\n"
            "The configured model achieved 91.8% accuracy on the test set."
        )
        raw_model_json = {
            "claims": [
                {
                    "quote": "Machine Learning (Random Forest)",
                    "subject": "project",
                    "attribute": "technology",
                    "value": "Random Forest",
                    "unit": None,
                },
                {
                    "quote": "Nitrogen (N)",
                    "subject": "project",
                    "attribute": "nutrient",
                    "value": "N",
                    "unit": None,
                },
                {
                    "quote": "Temperature",
                    "subject": "project",
                    "attribute": "feature",
                    "value": "Temperature",
                    "unit": None,
                },
                {
                    "quote": "Pomegranate",
                    "subject": "project",
                    "attribute": "crop",
                    "value": "Pomegranate",
                    "unit": None,
                },
                {
                    "quote": "Urea, DAP, MOP",
                    "subject": "project",
                    "attribute": "fertilizers",
                    "value": "Urea, DAP, MOP",
                    "unit": None,
                },
                {
                    "quote": "The configured model achieved 91.8% accuracy on the test set.",
                    "subject": "model",
                    "attribute": "accuracy",
                    "value": 91.8,
                    "unit": "%",
                },
            ]
        }

        raw_json_text = json.dumps(raw_model_json)
        claims = extract_claims(documentation, opener=MockOpener([raw_json_text]))

        self.assertEqual(
            [item.quote for item in claims],
            ["The configured model achieved 91.8% accuracy on the test set."],
        )
        self.assertEqual(len(claims), 1)
        self.assertEqual(json.loads(raw_json_text), raw_model_json)

    def test_claim_quality_filter_rejects_generic_fragments(self):
        fragments = [
            "Machine Learning (Random Forest)",
            "Crop_recommendation.csv",
            "Nitrogen (N)",
            "Temperature",
            "Pomegranate",
            "Urea, DAP, MOP",
        ]
        documentation = "\n".join(fragments)
        payload = {
            "claims": [
                {
                    "quote": fragment,
                    "subject": "project",
                    "attribute": "description",
                    "value": fragment,
                    "unit": None,
                }
                for fragment in fragments
            ]
        }

        claims = extract_claims(
            documentation,
            opener=MockOpener([json.dumps(payload)]),
        )

        self.assertEqual(claims, [])

    def test_numeric_claim_passes_claim_quality_filter(self):
        quote = "The validation accuracy was 91.8%."
        payload = {"claims": [claim(quote, value=91.8, unit="%")]}

        claims = extract_claims(
            quote,
            opener=MockOpener([json.dumps(payload)]),
        )

        self.assertEqual(claims[0].quote, quote)

    def test_explicit_configuration_claim_passes_claim_quality_filter(self):
        quote = "The configured model_name is Random Forest."
        payload = {
            "claims": [
                claim(
                    quote,
                    subject="project",
                    attribute="model_name",
                    value="Random Forest",
                    unit=None,
                )
            ]
        }

        claims = extract_claims(
            quote,
            opener=MockOpener([json.dumps(payload)]),
        )

        self.assertEqual(claims[0].attribute, "model_name")

    def test_prompt_excludes_non_verifiable_descriptive_content(self):
        prompt = extraction_prompt(
            "DNA Encoding Visualization\nBuilt with HTML5, CSS3, JavaScript, and GitHub Pages."
        )
        self.assertIn("concrete factual statements", prompt)
        self.assertIn("Ignore project descriptions", prompt)
        self.assertIn("feature headings", prompt)
        self.assertIn("technology", prompt)
        self.assertIn("name lists", prompt)
        self.assertIn("DNA Encoding Visualization", prompt)
        for technology in ("HTML5", "CSS3", "JavaScript", "GitHub Pages"):
            self.assertIn(technology, prompt)
        self.assertIn("standalone labels or bullets", prompt)

    def test_prompt_keeps_measurable_and_configured_facts(self):
        prompt = extraction_prompt(
            "Accuracy is 91.8%. The configured model_name is RandomForest."
        )
        self.assertIn("accuracy = 91.8%", prompt)
        self.assertIn("dataset_rows = 10000", prompt)
        self.assertIn("training_time = 42 seconds", prompt)
        self.assertIn("model_name such as RandomForest", prompt)

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

    def test_descriptive_documentation_can_return_no_claims(self):
        documentation = (
            "DNA Encoding Visualization\n"
            "Built with HTML5, CSS3, JavaScript, and GitHub Pages."
        )
        payload = {"claims": []}

        claims = extract_claims(
            documentation,
            opener=MockOpener([json.dumps(payload)]),
        )

        self.assertEqual(claims, [])

    def test_measurable_and_configured_examples_are_accepted(self):
        documentation = (
            "Accuracy is 91.8%. Precision is 0.80. Recall is 0.80. "
            "Training used 50 epochs and took 42 seconds. "
            "The configured model_name is RandomForest."
        )
        payload = {
            "claims": [
                claim("Accuracy is 91.8%.", attribute="accuracy", value=91.8, unit="%"),
                claim("Precision is 0.80.", attribute="precision", value=0.80, unit=None),
                claim("Recall is 0.80.", attribute="recall", value=0.80, unit=None),
                claim(
                    "Training used 50 epochs and took 42 seconds.",
                    subject="training",
                    attribute="epochs",
                    value=50,
                    unit=None,
                ),
                claim(
                    "The configured model_name is RandomForest.",
                    subject="project",
                    attribute="model_name",
                    value="RandomForest",
                    unit=None,
                ),
            ]
        }

        claims = extract_claims(
            documentation,
            opener=MockOpener([json.dumps(payload)]),
        )

        self.assertEqual(
            [item.attribute for item in claims],
            ["accuracy", "precision", "recall", "epochs", "model_name"],
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

    def test_configured_timeout_is_passed_to_http_opener(self):
        opener = MockOpener([json.dumps({"claims": [claim()]})])
        extract_claims(DOCUMENTATION, timeout=245, opener=opener)
        self.assertEqual(opener.requests[0][1], 245)

    def test_timeout_environment_variable_configures_http_opener(self):
        previous = os.environ.get("RECEIPTS_OLLAMA_TIMEOUT")
        os.environ["RECEIPTS_OLLAMA_TIMEOUT"] = "210"
        try:
            opener = MockOpener([json.dumps({"claims": [claim()]})])
            extract_claims(DOCUMENTATION, opener=opener)
            self.assertEqual(opener.requests[0][1], 210)
        finally:
            if previous is None:
                os.environ.pop("RECEIPTS_OLLAMA_TIMEOUT", None)
            else:
                os.environ["RECEIPTS_OLLAMA_TIMEOUT"] = previous

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
        opener = MockOpener([payload, payload])
        with self.assertRaisesRegex(AIExtractionError, "fabricated quote"):
            extract_claims(DOCUMENTATION, opener=opener)
        self.assertEqual(len(opener.requests), 2)

    def test_fabricated_quote_retries_and_valid_second_response_succeeds(self):
        fabricated = json.dumps({"claims": [claim("This sentence is not in the README.")]})
        valid = json.dumps({"claims": [claim()]})
        opener = MockOpener([fabricated, valid])

        claims = extract_claims(DOCUMENTATION, opener=opener)

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0].quote, claim()["quote"])
        self.assertEqual(len(opener.requests), 2)
        strict_prompt = json.loads(opener.requests[1][0].data.decode("utf-8"))["prompt"]
        self.assertIn("Do not include markdown fences", strict_prompt)

    def test_fabricated_quote_on_retry_fails_safely(self):
        fabricated = json.dumps({"claims": [claim("This sentence is not in the README.")]})
        opener = MockOpener([fabricated, fabricated])

        with self.assertRaisesRegex(AIExtractionError, "failed after one retry"):
            extract_claims(DOCUMENTATION, opener=opener)

        self.assertEqual(len(opener.requests), 2)

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

    def test_paraphrased_quote_is_grounded_to_source_passage(self):
        documentation = "Our model achieved 91.8% accuracy on the test set."
        payload = {
            "claims": [
                claim(
                    "The model got 91.8% accuracy.",
                    subject="model",
                    attribute="accuracy",
                    value=91.8,
                    unit="%",
                )
            ]
        }
        opener = MockOpener([json.dumps(payload)])

        claims = extract_claims(documentation, opener=opener)

        self.assertEqual(claims[0].quote, documentation)

    def test_paraphrase_with_no_grounding_fails_safely(self):
        documentation = "Our model achieved 91.8% accuracy on the test set."
        payload = {
            "claims": [
                claim(
                    "The model achieved 99.9% accuracy.",
                    subject="model",
                    attribute="accuracy",
                    value=99.9,
                    unit="%",
                )
            ]
        }
        opener = MockOpener([json.dumps(payload), json.dumps(payload)])

        with self.assertRaisesRegex(AIExtractionError, "failed after one retry"):
            extract_claims(documentation, opener=opener)

    def test_multiple_possible_grounding_passages_are_rejected(self):
        documentation = (
            "The model achieved 91.8% accuracy. "
            "The model achieved 91.8% accuracy."
        )
        payload = {
            "claims": [
                claim(
                    "The model got 91.8% accuracy.",
                    subject="model",
                    attribute="accuracy",
                    value=91.8,
                    unit="%",
                )
            ]
        }
        opener = MockOpener([json.dumps(payload), json.dumps(payload)])

        with self.assertRaisesRegex(AIExtractionError, "multiple source passages"):
            extract_claims(documentation, opener=opener)

    def test_grounding_works_for_arbitrary_readme_content(self):
        documentation = (
            "# Results\n\n"
            "After cleaning the sensor data, the classifier reached 73.5% recall "
            "on the validation split."
        )
        payload = {
            "claims": [
                claim(
                    "The classifier reached 73.5% recall.",
                    subject="classifier",
                    attribute="recall",
                    value=73.5,
                    unit="%",
                )
            ]
        }

        claims = extract_claims(documentation, opener=MockOpener([json.dumps(payload)]))

        self.assertEqual(
            claims[0].quote,
            "After cleaning the sensor data, the classifier reached 73.5% recall "
            "on the validation split.",
        )

    def test_grounding_normalizes_comma_formatted_numeric_anchor(self):
        documentation = "The evaluation used a dataset with 10,000 rows."
        payload = {
            "claims": [
                claim(
                    "The evaluation used 10000 rows.",
                    subject="evaluation",
                    attribute="dataset_rows",
                    value=10000,
                    unit=None,
                )
            ]
        }

        claims = extract_claims(documentation, opener=MockOpener([json.dumps(payload)]))

        self.assertEqual(claims[0].quote, documentation)

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
