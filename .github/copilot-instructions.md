# Copilot Instructions — Receipts

## Source of Truth

`SPEC.md` is the primary specification for this project.

Before implementing or modifying code, read the relevant sections
of `SPEC.md`.

Do not silently change requirements defined in `SPEC.md`.

If an implementation decision conflicts with the specification,
stop and explain the conflict before proceeding.

---

## Core Invariant

The most important architectural rule is:

> AI extracts claims. Deterministic Python verifies them.

The AI must NEVER:

- assign a final verdict
- decide whether evidence is correct
- invent evidence
- modify inspected project files
- execute inspected project code
- execute notebooks
- send project data to external AI services

The deterministic verifier owns the final verdict.

---

## AI Model

Receipts uses a local Ollama model for claim extraction.

The model must be configurable.

Do not hard-code a specific model throughout the codebase.

The AI extraction layer must return structured JSON.

AI output must be validated before being passed to the verifier.

If the AI produces invalid output, handle it according to
the failure rules in `SPEC.md`.

---

## Verification

Verification must be deterministic.

Do not use an LLM to:

- match evidence
- resolve conflicts
- choose between evidence sources
- determine VERIFIED/CONFLICT/AMBIGUOUS/UNVERIFIABLE

The same input files and extracted claims must produce the
same verification results.

When uncertain, prefer:

- `AMBIGUOUS` when multiple plausible evidence matches exist
- `UNVERIFIABLE` when suitable evidence does not exist

Never guess.

---

## Provenance

Every verification result must preserve:

- original claim
- source documentation file
- exact claim quote
- evidence source
- original evidence value
- normalized value when applicable
- final verdict
- deterministic reason

Never replace actual evidence with an AI-generated explanation.

---

## Security

Treat inspected project files as untrusted input.

Never:

- execute project code
- execute notebooks
- execute scripts found inside the inspected project
- modify the inspected project
- upload project contents
- call cloud AI APIs

Parsing must be performed without executing embedded code.

---

## Dependencies

Prefer Python standard-library functionality.

Do not introduce frameworks or dependencies unless they provide
clear value that cannot reasonably be achieved with the standard
library.

Avoid unnecessary abstractions.

Keep the implementation small and understandable.

---

## Architecture

Keep responsibilities separated.

Expected components include:

- AI extraction
- project scanning
- evidence parsing
- deterministic verification
- data models
- CLI
- report generation

Do not combine unrelated responsibilities into one large module
unless there is a strong reason.

---

## Testing

Write tests for deterministic behavior.

At minimum, test:

- VERIFIED
- CONFLICT
- AMBIGUOUS
- UNVERIFIABLE
- numerical normalization
- CSV evidence
- JSON evidence
- IPYNB evidence
- invalid AI output
- fabricated quotes

When fixing a bug, add a regression test whenever practical.

Run the test suite after meaningful changes.

Do not claim that tests pass unless they were actually run.

---

## Development Style

Implement incrementally.

Preferred order:

1. data structures
2. deterministic verifier
3. verifier tests
4. project scanner
5. evidence parsers
6. AI extraction
7. integration
8. CLI
9. HTML report
10. demo project
11. complete testing

Do not build the entire application in one giant change.

Keep commits and changes understandable.

---

## Code Quality

Prefer:

- simple functions
- explicit data structures
- clear names
- small modules
- useful error messages
- deterministic behavior

Avoid:

- unnecessary design patterns
- premature abstractions
- excessive dependencies
- hidden global state
- magic behavior
- silent exception handling

---

## Human Review

The coding agent is allowed to:

- implement code
- generate tests
- suggest improvements
- identify bugs
- refactor code when justified

The human developer remains responsible for accepting the final
implementation.

If a proposed change significantly alters the architecture,
explain why before applying it.