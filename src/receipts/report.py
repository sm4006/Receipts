"""Self-contained static HTML report generation."""

from collections import Counter
from html import escape
from pathlib import Path
from typing import Optional

from .pipeline import PipelineResult
from .verifier import (
    VERDICT_AMBIGUOUS,
    VERDICT_CONFLICT,
    VERDICT_UNVERIFIABLE,
    VERDICT_VERIFIED,
)


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _value(value: object) -> str:
    return _text(value) if value is not None else "unavailable"


def render_report(result: PipelineResult, project_path: str | Path) -> str:
    """Render deterministic pipeline data as a standalone HTML document."""
    counts = Counter(item.verdict for item in result.verification_results)
    project = str(project_path)
    rows = []
    for item in result.verification_results:
        claim = item.claim
        evidence = item.evidence
        evidence_source = "unavailable"
        evidence_location = ""
        evidence_value = "unavailable"
        if evidence is not None:
            evidence_source = evidence.source_file
            evidence_location = f" ({evidence.location})"
            evidence_value = repr(evidence.raw_value)
        rows.append(
            f"""      <article class="result {_text(item.verdict).lower()}">
        <h2>{_text(item.verdict)}</h2>
        <dl>
          <dt>Claim</dt><dd>{_text(claim.quote)}</dd>
          <dt>Source documentation</dt><dd>{_value(claim.source_file)}</dd>
          <dt>Evidence source</dt><dd>{_text(evidence_source)}{_text(evidence_location)}</dd>
          <dt>Evidence value</dt><dd>{_text(evidence_value)}</dd>
          <dt>Normalized claim value</dt><dd>{_value(item.normalized_claim_value)}</dd>
          <dt>Normalized evidence value</dt><dd>{_value(item.normalized_evidence_value)}</dd>
          <dt>Reason</dt><dd>{_text(item.reason)}</dd>
        </dl>
      </article>"""
        )
    result_markup = "\n".join(rows) if rows else '      <p class="empty">No verification results.</p>'
    errors_markup = ""
    if result.errors:
        errors_markup = (
            "    <section class=\"errors\"><h2>Errors</h2><ul>"
            + "".join(f"<li>{_text(error)}</li>" for error in result.errors)
            + "</ul></section>\n"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Receipts report - {_text(Path(project_path).name or project)}</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; }}
    body {{ max-width: 960px; margin: 2rem auto; padding: 0 1rem; color: #1f2937; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .75rem; }}
    .summary div {{ padding: .8rem; border-radius: .4rem; background: #f3f4f6; }}
    .summary strong {{ display: block; font-size: 1.4rem; }}
    .result {{ margin: 1.5rem 0; padding: 1rem 1.25rem; border-left: .45rem solid #6b7280; background: #f9fafb; }}
    .result h2 {{ margin-top: 0; }}
    .verified {{ border-color: #15803d; }} .conflict {{ border-color: #b91c1c; }}
    .ambiguous {{ border-color: #a16207; }} .unverifiable {{ border-color: #6b7280; }}
    dl {{ display: grid; grid-template-columns: 13rem 1fr; gap: .5rem 1rem; }}
    dt {{ font-weight: 700; }} dd {{ margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; }}
    .errors {{ padding: 1rem; background: #fef2f2; border: 1px solid #dc2626; }}
    .empty {{ color: #6b7280; }}
  </style>
</head>
<body>
  <h1>Receipts Verification Report</h1>
  <p><strong>Project:</strong> {_text(project)}</p>
  <section class="summary">
    <div>Claims<strong>{len(result.claims)}</strong></div>
    <div>VERIFIED<strong>{counts[VERDICT_VERIFIED]}</strong></div>
    <div>CONFLICT<strong>{counts[VERDICT_CONFLICT]}</strong></div>
    <div>AMBIGUOUS<strong>{counts[VERDICT_AMBIGUOUS]}</strong></div>
    <div>UNVERIFIABLE<strong>{counts[VERDICT_UNVERIFIABLE]}</strong></div>
  </section>
{errors_markup}  <main>
{result_markup}
  </main>
</body>
</html>
"""


def write_report(result: PipelineResult, project_path: str | Path, output_path: str | Path = "report.html") -> Path:
    """Write a self-contained report without reading or modifying the project."""
    destination = Path(output_path)
    destination.write_text(render_report(result, project_path), encoding="utf-8")
    return destination
