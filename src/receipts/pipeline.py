"""Internal orchestration for scanning, extraction, and verification."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List

from .extractor import AIExtractionError, extract_claims
from .models import Claim, VerificationResult
from .scanner import ScanResult, scan_project
from .verifier import verify_claim


@dataclass
class PipelineResult:
    scan: ScanResult
    claims: List[Claim] = field(default_factory=list)
    verification_results: List[VerificationResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def run_pipeline(
    project_dir: str | Path,
    extractor: Callable[..., List[Claim]] = extract_claims,
    verifier: Callable[..., VerificationResult] = verify_claim,
) -> PipelineResult:
    """Run the existing scanner, extractor, and deterministic verifier."""
    scan = scan_project(project_dir)
    result = PipelineResult(scan=scan, errors=list(scan.errors))
    if not Path(project_dir).is_dir():
        return result

    documentation = [
        item for item in scan.evidence
        if item.attribute == "documentation" and isinstance(item.value, str)
    ]
    for item in documentation:
        try:
            extracted = extractor(
                item.value,
                source_file=item.source_file,
            )
        except AIExtractionError as exc:
            result.errors.append(f"AI extraction failed for {item.source_file}: {exc}")
            continue
        result.claims.extend(extracted)

    for claim in result.claims:
        result.verification_results.append(verifier(claim, scan.evidence))
    return result
