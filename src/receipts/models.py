"""Small, JSON-compatible data structures used by the verifier."""

from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Claim:
    quote: str
    subject: str
    attribute: str
    value: Any
    unit: Optional[str] = None
    source_file: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    source_file: str
    location: str
    attribute: str
    value: Any
    unit: Optional[str] = None
    raw_value: Any = None
    subject: Optional[str] = None

    def __post_init__(self) -> None:
        if self.raw_value is None:
            object.__setattr__(self, "raw_value", self.value)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VerificationResult:
    claim: Claim
    evidence: Optional[Evidence]
    verdict: str
    reason: str
    normalized_claim_value: Any = None
    normalized_evidence_value: Any = None

    def to_dict(self) -> dict:
        result = asdict(self)
        result["claim"] = self.claim.to_dict()
        result["evidence"] = self.evidence.to_dict() if self.evidence else None
        return result
