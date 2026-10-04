# RECEIPTS

## 1. Project Overview

Receipts is a local AI-powered project documentation verification tool.

It checks whether factual claims made in project documentation
match the actual evidence present in the project files.

The core principle is:

> AI extracts claims. Deterministic Python verifies them.

## 2. Problem

Project documentation often becomes outdated or inaccurate.

For example, a README may claim:

"Our model achieved 94.2% accuracy."

while the actual results file contains:

accuracy,91.8%

Receipts should automatically identify this mismatch and
show the user exactly where the conflict exists.

## 3. Target User

College students and project teams who want to verify that
their project documentation matches their actual project files.

## 4. Core Principle

The AI must never make the final verification decision.

The AI is responsible for understanding documentation
and extracting structured factual claims.

Deterministic Python code is responsible for finding evidence,
comparing values, and producing the final verdict.

## 5. AI Contract

The local AI model is responsible only for extracting factual claims
from project documentation.

The AI must return structured JSON.

Each claim should contain:

- `quote` — the exact sentence or text from the documentation
- `subject` — what the claim is about
- `attribute` — the property being claimed
- `value` — the claimed value
- `unit` — the unit, if applicable

Example:

{
  "claims": [
    {
      "quote": "Our Random Forest model achieved 94.2% accuracy.",
      "subject": "Random Forest model",
      "attribute": "accuracy",
      "value": 94.2,
      "unit": "%"
    }
  ]
}

The AI must not:

- decide whether a claim is true
- choose the final verdict
- invent evidence
- modify project files
- create evidence that does not exist

## 6. Supported Inputs

Receipts operates on a project folder.

For the MVP, it supports:

- `README.md` — primary documentation source
- `.csv` — tabular results and metrics
- `.json` — configuration and structured project data
- `.ipynb` — Jupyter notebooks

The MVP does not support PDF, DOCX, images, or other formats.

## 7. Evidence Rules

Evidence must come from files that actually exist inside the
user's project folder.

The deterministic verification engine is responsible for:

1. Reading supported project files.
2. Extracting available factual values.
3. Matching evidence to extracted claims.
4. Comparing the claimed value with the actual evidence.
5. Producing the final verdict.

The AI must not invent, modify, or supply evidence.

Every verification result should retain the source file and
the relevant evidence so the user can understand why the
verdict was produced.

## 8. Verification Verdicts

Every extracted claim must receive exactly one final verdict.

### VERIFIED

The available project evidence matches the claim.

Example:

Documentation:
"Our model achieved 91.8% accuracy."

Evidence:
results.csv → accuracy = 91.8%

Verdict:
VERIFIED

### CONFLICT

Reliable project evidence contradicts the claim.

Example:

Documentation:
"Our model achieved 94.2% accuracy."

Evidence:
results.csv → accuracy = 91.8%

Verdict:
CONFLICT

### AMBIGUOUS

Multiple plausible pieces of evidence exist and the system
cannot safely determine which evidence applies to the claim.

The system must not guess.

### UNVERIFIABLE

No suitable evidence exists in the supported project files.

UNVERIFIABLE does not mean the claim is false. It means
Receipts could not verify it from the available evidence.

## 9. Verdict Authority

The final verdict must be produced by deterministic Python
verification logic.

The AI must never directly assign a verdict.

If the available evidence is insufficient or conflicting,
the system must prefer AMBIGUOUS or UNVERIFIABLE rather
than guessing.

## 10. Provenance

Every verification result must show enough information for the
user to understand and audit the result.

Each result should contain:

- The original claim.
- The source documentation file.
- The exact quoted text containing the claim.
- The evidence file used for verification, when available.
- The relevant evidence value.
- The final verdict.
- A short deterministic explanation of the comparison.

Example:

CLAIM
"Our Random Forest model achieved 94.2% accuracy."

SOURCE
README.md

EVIDENCE
results.csv
accuracy = 91.8%

VERDICT
CONFLICT

REASON
The documented accuracy (94.2%) does not match the recorded
accuracy (91.8%) in results.csv.

Receipts must never hide the evidence behind an AI-generated
explanation. The underlying source and values must remain visible.

## 11. Verification Algorithm

For every extracted claim, Receipts must perform verification
using deterministic Python logic.

The verification process is:

1. Read the claim extracted by the AI.
2. Normalize the claim's subject, attribute, value, and unit.
3. Search supported project files for relevant evidence.
4. Identify all plausible evidence matches.
5. Normalize evidence values into comparable forms.
6. Compare the claimed value with the evidence value.
7. Determine the verdict using deterministic rules.
8. Store the claim, evidence, source files, comparison, and verdict.

### Matching Rules

The system should use deterministic matching based on:

- normalized attribute names
- known metric aliases
- normalized numerical values
- file content and structure

Examples of metric aliases may include:

- `accuracy` ↔ `acc`
- `dataset size` ↔ `dataset_rows`
- `epochs` ↔ `training_epochs`

The alias list must remain explicit and inspectable.

### Numerical Normalization

Equivalent representations should be treated as equal.

Examples:

- `91.8%` → `91.8`
- `0.918` → `91.8%`
- `91.80` → `91.8`

The system must preserve the original representation for
provenance while using normalized values for comparison.

### Multiple Matches

If multiple plausible evidence values match the same claim
and the system cannot determine which one is authoritative,
the result must be:

AMBIGUOUS

The system must never guess.

### No Evidence

If no suitable evidence can be found, the result must be:

UNVERIFIABLE

### Deterministic Authority

Once the AI has extracted a claim, the verification result
must not depend on another AI-generated decision.

The same project files and same extracted claim should produce
the same verification result.

## 12. AI Failure Handling

The AI extraction stage must be treated as an unreliable input
source.

Receipts must safely handle malformed, incomplete, or incorrect
AI responses.

### Invalid JSON

If the AI does not return valid JSON:

1. Attempt a safe JSON extraction if possible.
2. Validate the resulting structure.
3. Retry the AI request once with a stricter JSON-only prompt.
4. If the response is still invalid, stop extraction and report
   an AI extraction error.

The verifier must never receive unvalidated AI output.

### Invalid Claim Structure

Every claim must contain the required fields:

- `quote`
- `subject`
- `attribute`
- `value`
- `unit`

If required fields are missing, the claim must be rejected.

### Fabricated Quotes

The AI must provide the exact text from the documentation.

Receipts must verify that the supplied `quote` actually exists
in the source documentation.

If the quote cannot be found, the claim must be rejected rather
than verified.

### Unsupported Claims

If the AI extracts a claim that cannot be represented by the
supported verification system, the claim should be marked as
UNVERIFIABLE rather than guessed.

### AI Availability

If Ollama is unavailable or the configured model cannot be
reached, Receipts must display a clear error explaining that
local AI extraction is unavailable.

The program must not silently fall back to an external API.

### No Silent Failure

Errors during AI extraction, file parsing, or verification must
be visible to the user.

Receipts must prefer an explicit error over a misleading result.

## 13. Project File Parsing

Receipts must parse supported project files using deterministic
Python code.

### README.md

The README is the primary documentation source.

Receipts should preserve the original text so that extracted
quotes can be checked against the source.

### CSV

CSV files should be parsed using Python's standard CSV parser.

The parser should expose:

- column names
- rows
- numerical values
- textual values

### JSON

JSON files should be parsed using Python's standard JSON parser.

Nested objects and arrays should be traversable when searching
for evidence.

### Jupyter Notebook

`.ipynb` files are JSON documents.

Receipts should inspect notebook cells and extract relevant
textual and structured content.

The MVP should not execute notebooks.

### Unsupported Files

Unsupported file types must be ignored rather than interpreted
speculatively.

Receipts must never execute arbitrary project files during
verification.

## 14. Architecture

Receipts should use a small modular Python architecture.

The main components are:

### AI Extractor

Responsible for:

- sending documentation to the local Ollama model
- requesting structured claim extraction
- validating the returned JSON
- returning normalized claim objects

The AI extractor must not perform verification.

### Project Scanner

Responsible for:

- discovering supported files
- reading project files
- identifying file types
- passing content to the appropriate parser

### Evidence Parser

Responsible for converting supported project files
into searchable evidence.

### Deterministic Verifier

Responsible for:

- matching claims with evidence
- normalizing values
- comparing values
- assigning the final verdict
- preserving provenance

### Report Generator

Responsible for creating:

- terminal output
- static `report.html`

The report generator must display the actual evidence and
verification reasoning.

### CLI

The command-line interface should provide a simple way to run
Receipts against a project directory.

Example:

receipts ./my-project

The CLI should also provide useful errors for invalid paths,
missing files, and unavailable Ollama.

## 15. Data Structures

Receipts should use simple JSON-compatible Python data structures.

### Claim

A claim should contain:

- `quote`
- `subject`
- `attribute`
- `value`
- `unit`

Example:

{
  "quote": "Our model achieved 94.2% accuracy.",
  "subject": "Random Forest model",
  "attribute": "accuracy",
  "value": 94.2,
  "unit": "%"
}

### Evidence

Evidence should contain:

- `source_file`
- `location`
- `attribute`
- `value`
- `unit`
- `raw_value`

### Verification Result

A verification result should contain:

- `claim`
- `evidence`
- `verdict`
- `reason`

The result must preserve the original claim and evidence
without replacing them with AI-generated summaries.

## 16. Local AI Model

Receipts must use a locally running Ollama model for claim
extraction.

The model must be configurable and must not be hard-coded
throughout the application.

The application should use an environment variable or CLI
option for selecting the model.

Example:

RECEIPTS_MODEL=gemma-model-name

The default model should be documented in the README.

Receipts must communicate with Ollama locally.

No project files or project contents should be sent to an
external AI API.

The application must fail clearly if Ollama is unavailable.

The AI model is used only for claim extraction.

All evidence matching and verdict generation must remain
deterministic Python logic.

## 17. CLI Requirements

The MVP must provide a simple command-line interface.

Basic usage:

receipts <project-directory>

Example:

receipts ./demo/project

The CLI should:

1. Validate the project directory.
2. Discover supported files.
3. Extract documentation claims.
4. Verify the claims.
5. Print a concise verification summary.
6. Generate the HTML report.

The terminal output should clearly show:

- total claims
- verified claims
- conflicts
- ambiguous claims
- unverifiable claims
- errors

Example:

Receipts Verification

Claims:       8
Verified:     2
Conflicts:    3
Ambiguous:    1
Unverifiable: 2

Report: report.html

## 18. HTML Report

Receipts must generate a self-contained static HTML report.

The report must work by opening the HTML file locally.

The report should contain:

- project name
- verification summary
- individual claim results
- source documentation
- evidence source
- original values
- normalized values when relevant
- verdict
- deterministic reason

Each verdict should be visually distinguishable.

The report must not require an internet connection.

The report must not send project data to an external service.

The HTML report should prioritize auditability over visual
complexity.

## 19. Security and Privacy

Receipts is designed for local project verification.

Project contents must remain on the user's machine.

The MVP must:

- use local Ollama inference
- avoid external AI APIs
- avoid uploading project files
- avoid executing project code
- avoid executing Jupyter notebooks
- avoid modifying the inspected project
- avoid collecting telemetry

The tool should treat project files as untrusted input.

File parsing must therefore be performed without executing
embedded code.

Generated reports should contain only information derived from
the inspected project.

## 20. Testing Requirements

Receipts must include automated tests for the deterministic
verification engine.

Tests must cover at minimum:

### VERIFIED

A documentation claim exactly matches reliable evidence.

### CONFLICT

A documentation claim contradicts reliable evidence.

### AMBIGUOUS

Multiple equally plausible evidence values exist.

### UNVERIFIABLE

No suitable evidence exists.

### Numerical Normalization

Equivalent numerical representations should be handled
correctly.

### Multiple File Types

Evidence should be discoverable from:

- CSV
- JSON
- IPYNB

### Invalid AI Output

Malformed AI responses must not reach the verifier.

### Fabricated Quote

A claim containing a quote that does not exist in the source
documentation must be rejected.

### Regression Tests

Every bug discovered during development should receive a
regression test.

## 21. Demo Dataset

The repository must contain a small synthetic project demonstrating
the complete verification workflow.

The demo project should contain:

- `README.md`
- `results.csv`
- `config.json`
- `analysis.ipynb`

The README should intentionally contain a mixture of correct
and incorrect factual claims.

The demo should demonstrate all four verdict types:

- VERIFIED
- CONFLICT
- AMBIGUOUS
- UNVERIFIABLE

The demo must be deterministic and must not depend on external
data or network access.

## 22. Repository Structure

The expected repository structure is:

receipts/
├── README.md
├── SPEC.md
├── LICENSE
├── .gitignore
├── .github/
│   └── copilot-instructions.md
├── src/
│   └── receipts/
│       ├── __init__.py
│       ├── cli.py
│       ├── extractor.py
│       ├── scanner.py
│       ├── parsers.py
│       ├── verifier.py
│       ├── models.py
│       └── report.py
├── tests/
├── demo/
│   └── sample_project/
└── report.html


---

# Section 23 — Dependencies

```markdown
## 23. Dependencies

The MVP should minimize runtime dependencies.

Python standard-library modules should be preferred for:

- CSV parsing
- JSON parsing
- filesystem operations
- regular expressions
- numerical normalization
- HTML generation
- HTTP communication with Ollama

Ollama is the only required external runtime service.

Testing dependencies may be used during development.

A dependency should only be introduced when it provides
substantial value that cannot reasonably be achieved with
the Python standard library.

## 24. AI Coding Agent Instructions

The implementation should be developed with an AI coding agent
such as GitHub Copilot.

The coding agent must follow this specification as the source
of truth.

The coding agent must not:

- replace deterministic verification with AI reasoning
- introduce unnecessary frameworks
- add cloud AI APIs
- execute inspected project code
- modify inspected project files
- silently ignore verification errors
- invent evidence
- weaken provenance requirements

The coding agent should:

- implement one component at a time
- write tests alongside deterministic logic
- keep modules small
- preserve clear interfaces
- run tests after changes
- explain significant architectural decisions
- prefer simple implementations over abstractions

Any deviation from this specification must be explicitly
identified and justified.

## 25. Acceptance Criteria

The MVP is complete when all of the following are true:

- A user can provide a project directory.
- Receipts can discover supported project files.
- README claims can be extracted using a local Ollama model.
- AI output is validated before entering the verifier.
- Evidence can be extracted from CSV, JSON, and IPYNB files.
- Verification is performed deterministically.
- The AI never decides the final verdict.
- All four verdict types are supported.
- Source provenance is preserved.
- The demo project produces predictable results.
- Automated tests cover the verification engine.
- A self-contained HTML report is generated.
- The CLI provides a clear summary.
- No project data is sent to an external API.
- The inspected project is never executed or modified.
- The application works without an internet connection once
  Ollama and the required model are installed.
- The repository contains clear documentation explaining the
  architecture and local AI approach.

  ## 26. Non-Goals

The MVP will NOT attempt to:

- verify arbitrary natural-language claims
- understand every possible project file format
- execute source code
- execute notebooks
- verify visual claims from images
- verify PDFs or DOCX files
- browse the internet for evidence
- determine whether a project itself is correct
- judge whether a model is scientifically valid
- replace human review
- provide legal, academic, or scientific certification
- use an external cloud AI service
- automatically rewrite project documentation

These features may be considered future work.

## 27. Future Work

Possible future improvements include:

- PDF and DOCX support
- image and chart verification
- additional project file formats
- stronger semantic metric matching
- Git history comparison
- CI/CD integration
- GitHub Actions support
- pre-commit verification
- IDE integration
- richer HTML reports
- additional local AI models
- configurable verification rules
- project-specific schemas

## 28. Development Workflow

Receipts should be developed specification-first.

The development process is:

1. Define requirements in `SPEC.md`.
2. Create the repository structure.
3. Configure the coding agent using
   `.github/copilot-instructions.md`.
4. Implement the deterministic verification engine first.
5. Write tests for the verification engine.
6. Implement supported file parsers.
7. Implement the local Ollama AI extraction layer.
8. Connect AI extraction to deterministic verification.
9. Build the CLI.
10. Build the static HTML report.
11. Create the deterministic demo project.
12. Run the complete test suite.
13. Perform adversarial testing with intentionally incorrect
    documentation.
14. Fix discovered issues.
15. Review the final implementation against every requirement
    in this specification.

AI coding tools may implement code, suggest changes, generate
tests, and identify bugs.

However, architectural decisions and acceptance criteria are
defined by this specification.

Human review remains responsible for accepting the final result.