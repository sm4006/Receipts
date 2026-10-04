"""Command-line presentation for the existing Receipts pipeline."""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Optional, Sequence, TextIO

from .pipeline import PipelineResult, run_pipeline
from .report import write_report
from .verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="receipts",
        description="Verify documented project claims against project evidence.",
    )
    parser.add_argument("project_directory", help="project directory to verify")
    return parser


def _print_result(result, output: TextIO) -> None:
    claim = result.claim
    print(f"VERDICT: {result.verdict}", file=output)
    print(f"CLAIM: {claim.quote}", file=output)
    print(f"SOURCE: {claim.source_file or 'unknown'}", file=output)
    if result.evidence is not None:
        evidence = result.evidence
        print(
            f"EVIDENCE: {evidence.source_file} ({evidence.location})",
            file=output,
        )
        print(f"EVIDENCE VALUE: {evidence.raw_value!r}", file=output)
    else:
        print("EVIDENCE: unavailable", file=output)
    print(f"REASON: {result.reason}", file=output)
    print(file=output)


def _print_summary(result: PipelineResult, output: TextIO) -> None:
    counts = Counter(item.verdict for item in result.verification_results)
    print("SUMMARY", file=output)
    print(f"Claims:       {len(result.claims)}", file=output)
    print(f"VERIFIED:     {counts[VERDICT_VERIFIED]}", file=output)
    print(f"CONFLICT:     {counts[VERDICT_CONFLICT]}", file=output)
    print(f"AMBIGUOUS:    {counts[VERDICT_AMBIGUOUS]}", file=output)
    print(f"UNVERIFIABLE: {counts[VERDICT_UNVERIFIABLE]}", file=output)
    if result.errors:
        print("ERRORS:", file=output)
        for error in result.errors:
            print(f"- {error}", file=output)


def main(
    argv: Optional[Sequence[str]] = None,
    pipeline: Callable[[str | Path], PipelineResult] = run_pipeline,
    report_writer: Callable[..., Path] = write_report,
    output: TextIO = sys.stdout,
    errors: TextIO = sys.stderr,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print("Error: project path is required.", file=errors)
        return 2
    args = _parser().parse_args(arguments)
    project_path = Path(args.project_directory)
    if not project_path.exists():
        print(f"Error: project path does not exist: {project_path}", file=errors)
        return 2
    if not project_path.is_dir():
        print(f"Error: project path is not a directory: {project_path}", file=errors)
        return 2

    result = pipeline(project_path)
    print("Receipts Verification", file=output)
    print(file=output)
    for verification in result.verification_results:
        _print_result(verification, output)
    _print_summary(result, output)
    if result.errors:
        return 1
    try:
        report_path = report_writer(result, project_path, "report.html")
    except OSError as exc:
        print(f"Error: could not generate report.html: {exc}", file=errors)
        return 1
    print(f"Report: {report_path}", file=output)
    return 0
