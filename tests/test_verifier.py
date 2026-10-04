import unittest
from decimal import Decimal

from receipts.models import Claim, Evidence
from receipts.verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
    normalize_attribute,
    normalize_number,
    verify_claim,
)


def evidence(attribute, value, unit=None, source_file="results.csv", subject=None):
    return Evidence(source_file, "row 2", attribute, value, unit, subject=subject)


class VerifierTests(unittest.TestCase):
    def test_verified_using_metric_alias_and_provenance(self):
        claim = Claim("Accuracy was 91.8%.", "model", "accuracy", 91.8, "%", "README.md")
        result = verify_claim(claim, [evidence("acc", "91.80%", "%")])
        self.assertEqual(result.verdict, VERDICT_VERIFIED)
        self.assertEqual(result.evidence.raw_value, "91.80%")
        self.assertEqual(result.claim.quote, "Accuracy was 91.8%.")

    def test_conflict(self):
        claim = Claim("Accuracy was 94.2%.", "model", "accuracy", 94.2, "%")
        result = verify_claim(claim, [evidence("acc", 91.8, "%")])
        self.assertEqual(result.verdict, VERDICT_CONFLICT)
        self.assertEqual(result.normalized_evidence_value, Decimal("91.8"))

    def test_explicitly_mismatched_units_conflict(self):
        claim = Claim("Accuracy was 91.8%.", "model", "accuracy", 91.8, "%")
        result = verify_claim(claim, [evidence("accuracy", 91.8, "milliseconds")])
        self.assertEqual(result.verdict, VERDICT_CONFLICT)

    def test_ambiguous(self):
        claim = Claim("There were 100 rows.", "dataset", "dataset size", 100)
        result = verify_claim(claim, [evidence("dataset_rows", 100), evidence("dataset_rows", 100)])
        self.assertEqual(result.verdict, VERDICT_AMBIGUOUS)
        self.assertIsNone(result.evidence)

    def test_unverifiable(self):
        claim = Claim("There were 10 epochs.", "model", "epochs", 10)
        result = verify_claim(claim, [evidence("accuracy", 0.9)])
        self.assertEqual(result.verdict, VERDICT_UNVERIFIABLE)

    def test_fabricated_quote_without_evidence_is_not_verified(self):
        claim = Claim(
            "The model achieved a fabricated accuracy of 99.9%.",
            "model",
            "accuracy",
            99.9,
            "%",
            "README.md",
        )
        result = verify_claim(claim, [])
        self.assertEqual(result.verdict, VERDICT_UNVERIFIABLE)
        self.assertIsNone(result.evidence)

    def test_numerical_normalization(self):
        self.assertEqual(normalize_number("91.8%", "%"), Decimal("91.8"))
        self.assertEqual(normalize_number("0.918", "%"), Decimal("91.8"))
        self.assertEqual(normalize_number("0.918", "percent"), Decimal("91.8"))
        self.assertEqual(normalize_number("91.80"), Decimal("91.8"))
        self.assertIsNone(normalize_number("not-a-number"))

    def test_aliases_are_explicit(self):
        self.assertEqual(normalize_attribute("accuracy"), "accuracy")
        self.assertEqual(normalize_attribute("acc"), "accuracy")
        self.assertEqual(normalize_attribute("dataset_rows"), "dataset_rows")
        self.assertEqual(normalize_attribute("training-epochs"), "training_epochs")

    def test_dataset_size_and_epochs_aliases_match_deterministically(self):
        dataset_claim = Claim("The dataset has 100 rows.", "dataset", "dataset size", 100)
        epochs_claim = Claim("Training ran for 12 epochs.", "model", "epochs", 12)
        dataset_result = verify_claim(dataset_claim, [evidence("dataset_rows", 100)])
        epochs_result = verify_claim(epochs_claim, [evidence("training_epochs", 12)])
        self.assertEqual(dataset_result.verdict, VERDICT_VERIFIED)
        self.assertEqual(epochs_result.verdict, VERDICT_VERIFIED)

    def test_result_preserves_complete_provenance(self):
        claim = Claim(
            "The model achieved 91.8% accuracy.",
            "model",
            "accuracy",
            "0.918",
            "%",
            "README.md",
        )
        matched = Evidence(
            "metrics.json",
            "$.acc",
            "acc",
            "91.80%",
            "%",
            raw_value="91.80%",
            subject="model",
        )
        result = verify_claim(claim, [matched])
        self.assertEqual(result.verdict, VERDICT_VERIFIED)
        self.assertEqual(result.claim.to_dict(), claim.to_dict())
        self.assertEqual(result.evidence.to_dict(), matched.to_dict())
        self.assertEqual(result.evidence.source_file, "metrics.json")
        self.assertEqual(result.evidence.location, "$.acc")
        self.assertEqual(result.evidence.raw_value, "91.80%")
        self.assertEqual(result.normalized_claim_value, Decimal("91.8"))
        self.assertEqual(result.normalized_evidence_value, Decimal("91.8"))


if __name__ == "__main__":
    unittest.main()
