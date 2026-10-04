"""Deterministic verification primitives for Receipts."""

from .models import Claim, Evidence, VerificationResult
from .scanner import ScanResult, scan_project
from .extractor import (
    AIExtractionError,
    ExtractionConfig,
    LocalAIUnavailableError,
    extract_claims,
)
from .pipeline import PipelineResult, run_pipeline
from .report import render_report, write_report
from .verifier import VERDICT_AMBIGUOUS, VERDICT_CONFLICT, VERDICT_UNVERIFIABLE, VERDICT_VERIFIED, verify_claim

__all__ = [
    "Claim",
    "Evidence",
    "VerificationResult",
    "ScanResult",
    "scan_project",
    "AIExtractionError",
    "ExtractionConfig",
    "LocalAIUnavailableError",
    "extract_claims",
    "PipelineResult",
    "run_pipeline",
    "render_report",
    "write_report",
    "verify_claim",
    "VERDICT_VERIFIED",
    "VERDICT_CONFLICT",
    "VERDICT_AMBIGUOUS",
    "VERDICT_UNVERIFIABLE",
]
