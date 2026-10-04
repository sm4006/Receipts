# Receipts

Receipts checks whether factual claims in a project's documentation match
evidence stored in the project files.

## Why it exists

Project reports and README files can become stale as experiments change. A
student may document one accuracy value while a results file contains another.
Receipts makes those mismatches visible, with the source file and evidence
value needed for a quick audit.

## How it works

1. Receipts scans the supplied project directory for `README.md`, CSV, JSON,
   and Jupyter Notebook files.
2. Local Ollama extracts structured claims from documentation.
3. Python parses the supported evidence files without executing project code
   or notebooks.
4. Deterministic Python matches evidence, normalizes values, and assigns the
   final `VERIFIED`, `CONFLICT`, `AMBIGUOUS`, or `UNVERIFIABLE` verdict.

The AI extracts claims only. It never supplies evidence or decides a verdict.
Project contents stay on the local machine and are not sent to a cloud AI
service.

## Requirements

- Python 3.10 or newer
- Ollama
- A local Ollama model; the default is `gemma3:4b`

The application uses only the Python standard library at runtime.

## Setup

Install and start Ollama, then download the default model:

```text
ollama pull gemma3:4b
ollama serve
```

If Ollama is already running as a service, only the `pull` command is
needed. To use another local model, set `RECEIPTS_OLLAMA_MODEL`:

```powershell
$env:RECEIPTS_OLLAMA_MODEL = "llama3.2:3b"
```

From the project root, expose the source package for a checkout that has not
been installed as a package:

```powershell
$env:PYTHONPATH = "src"
```

## Run Receipts

Verify any project directory:

```powershell
python -m receipts <project-directory>
```

Run the included deterministic demo:

```powershell
python -m receipts demo\receipts_demo
```

The demo contains seven claims and is designed to show all four verdicts.
With Ollama and Gemma 3 4B available, the expected summary is:

```text
Claims:       7
VERIFIED:     2
CONFLICT:     2
AMBIGUOUS:    1
UNVERIFIABLE: 2
```

The terminal output also shows each claim, its documentation source, matched
evidence when available, and the deterministic reason.

## HTML reports

The static report layer can write a self-contained report from a pipeline
result:

```python
from pathlib import Path

from receipts.pipeline import run_pipeline
from receipts.report import write_report

project = Path("demo") / "receipts_demo"
result = run_pipeline(project)
write_report(result, project, "report.html")
```

Open `report.html` directly in a browser. It has no external assets,
JavaScript framework, network request, or telemetry.

## Development and tests

Run the complete standard-library test suite:

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

The tests cover deterministic verdicts, numerical normalization, CSV/JSON/
IPYNB evidence, AI validation, provenance, CLI behavior, reporting, and the
demo fixture.