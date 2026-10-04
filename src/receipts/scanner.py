"""Safe discovery and parsing of supported project evidence files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List
import csv
import json

from .models import Evidence
from .parsers import parse_csv, parse_ipynb, parse_json, parse_readme

Parser = Callable[[Path], List[Evidence]]
PARSERS: Dict[str, Parser] = {
    ".csv": parse_csv,
    ".json": parse_json,
    ".ipynb": parse_ipynb,
}


@dataclass
class ScanResult:
    evidence: List[Evidence] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    files: List[str] = field(default_factory=list)


def _supported_parser(path: Path) -> Parser | None:
    if path.name == "README.md":
        return parse_readme
    return PARSERS.get(path.suffix.lower())


def scan_project(project_dir: str | Path) -> ScanResult:
    root = Path(project_dir)
    result = ScanResult()
    if not root.is_dir():
        result.errors.append(f"Project directory is not readable: {root}")
        return result

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        parser = _supported_parser(path)
        if parser is None:
            continue
        relative_name = str(path.relative_to(root))
        result.files.append(relative_name)
        try:
            parsed = parser(path)
        except (OSError, UnicodeError, ValueError, csv.Error, json.JSONDecodeError) as exc:
            result.errors.append(f"{relative_name}: {exc}")
            continue
        result.evidence.extend(
            Evidence(
                source_file=relative_name,
                location=item.location,
                attribute=item.attribute,
                value=item.value,
                unit=item.unit,
                raw_value=item.raw_value,
                subject=item.subject,
            )
            for item in parsed
        )
    return result
