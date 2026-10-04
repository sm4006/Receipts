"""Deterministic claim-to-evidence verification."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from .models import Claim, Evidence, VerificationResult

VERDICT_VERIFIED = "VERIFIED"
VERDICT_CONFLICT = "CONFLICT"
VERDICT_AMBIGUOUS = "AMBIGUOUS"
VERDICT_UNVERIFIABLE = "UNVERIFIABLE"

METRIC_ALIASES = {
    "accuracy": "accuracy",
    "acc": "accuracy",
    "dataset size": "dataset_rows",
    "dataset rows": "dataset_rows",
    "dataset_rows": "dataset_rows",
    "epochs": "training_epochs",
    "training epochs": "training_epochs",
    "training_epochs": "training_epochs",
}


def normalize_attribute(attribute: str) -> str:
    key = re.sub(r"[_\s-]+", " ", attribute.strip().lower())
    return METRIC_ALIASES.get(key, key)


def normalize_number(value: Any, unit: Optional[str] = None) -> Optional[Decimal]:
    """Return a finite comparable number without changing the source value."""
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace(",", "")
    normalized_unit = (unit or "").strip().casefold()
    is_percent = text.endswith("%") or normalized_unit in {"%", "percent", "percentage"}
    if text.endswith("%"):
        text = text[:-1].strip()
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    if is_percent and Decimal("0") <= number <= Decimal("1"):
        number *= Decimal("100")
    return number.normalize()


def _normalized_value(value: Any, unit: Optional[str], comparison_unit: Optional[str]) -> Any:
    number = normalize_number(value, unit or comparison_unit)
    if number is not None:
        return number
    return str(value).strip().casefold()


def _units_compatible(claim_unit: Optional[str], evidence_unit: Optional[str]) -> bool:
    """Reject explicit unit mismatches while allowing omitted units."""
    if not claim_unit or not evidence_unit:
        return True
    aliases = {"percent": "%", "percentage": "%"}
    normalized = {
        aliases.get(claim_unit.strip().casefold(), claim_unit.strip().casefold()),
        aliases.get(evidence_unit.strip().casefold(), evidence_unit.strip().casefold()),
    }
    return len(normalized) == 1


def _matches(claim: Claim, evidence: Evidence) -> bool:
    if normalize_attribute(claim.attribute) != normalize_attribute(evidence.attribute):
        return False
    if claim.subject and evidence.subject:
        return claim.subject.strip().casefold() == evidence.subject.strip().casefold()
    return True


def verify_claim(claim: Claim, evidence: Iterable[Evidence]) -> VerificationResult:
    """Verify one claim against already-parsed evidence, without reading files."""
    candidates = [item for item in evidence if _matches(claim, item)]
    if not candidates:
        return VerificationResult(
            claim=claim,
            evidence=None,
            verdict=VERDICT_UNVERIFIABLE,
            reason="No suitable evidence matches the claim attribute.",
        )
    if len(candidates) > 1:
        return VerificationResult(
            claim=claim,
            evidence=None,
            verdict=VERDICT_AMBIGUOUS,
            reason="Multiple plausible evidence entries match the claim.",
        )

    selected = candidates[0]
    claim_value = _normalized_value(claim.value, claim.unit, selected.unit)
    evidence_value = _normalized_value(selected.value, selected.unit, claim.unit)
    equal = _units_compatible(claim.unit, selected.unit) and claim_value == evidence_value
    verdict = VERDICT_VERIFIED if equal else VERDICT_CONFLICT
    reason = (
        "The claim value matches the evidence value after normalization."
        if equal
        else "The claim value does not match the evidence value after normalization."
    )
    return VerificationResult(
        claim=claim,
        evidence=selected,
        verdict=verdict,
        reason=reason,
        normalized_claim_value=claim_value,
        normalized_evidence_value=evidence_value,
    )
