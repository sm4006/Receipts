"""Safe parsers for the supported project evidence formats."""

import csv
import json
from pathlib import Path
from typing import Any, Iterator, List

from .models import Evidence


def _leaf_values(value: Any, location: str) -> Iterator[tuple[str, Any, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else str(key)
            yield from _leaf_values(child, child_location)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaf_values(child, f"{location}[{index}]")
    else:
        yield location or "$", value, location or "$"


def parse_readme(path: Path) -> List[Evidence]:
    text = path.read_text(encoding="utf-8")
    return [
        Evidence(
            source_file=path.name,
            location="document",
            attribute="documentation",
            value=text,
            raw_value=text,
        )
    ]


def parse_csv(path: Path) -> List[Evidence]:
    evidence: List[Evidence] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, strict=True)
        try:
            headers = next(reader)
        except StopIteration:
            return evidence
        if not headers or any(not header.strip() for header in headers):
            raise ValueError("CSV must contain non-empty column names")
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(headers):
                raise ValueError(f"CSV row {row_number} has {len(row)} values; expected {len(headers)}")
            for header, raw_value in zip(headers, row):
                evidence.append(
                    Evidence(
                        source_file=path.name,
                        location=f"row {row_number}, column {header}",
                        attribute=header,
                        value=raw_value,
                        raw_value=raw_value,
                    )
                )
    return evidence


def parse_json(path: Path) -> List[Evidence]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return [
        Evidence(
            source_file=path.name,
            location=location,
            attribute=location.rsplit(".", 1)[-1].split("[", 1)[0],
            value=value,
            raw_value=value,
        )
        for location, value, _ in _leaf_values(data, "$")
    ]


def parse_ipynb(path: Path) -> List[Evidence]:
    with path.open("r", encoding="utf-8") as handle:
        notebook = json.load(handle)
    if not isinstance(notebook, dict):
        raise ValueError("Notebook must be a JSON object")
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise ValueError("Notebook must contain a cells list")

    evidence: List[Evidence] = []
    for cell_index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise ValueError(f"Notebook cell {cell_index} is not an object")
        source = cell.get("source", "")
        if isinstance(source, list):
            if not all(isinstance(part, str) for part in source):
                raise ValueError(f"Notebook cell {cell_index} has invalid source")
            source = "".join(source)
        if not isinstance(source, str):
            raise ValueError(f"Notebook cell {cell_index} has invalid source")
        if source:
            cell_type = cell.get("cell_type", "unknown")
            evidence.append(
                Evidence(
                    source_file=path.name,
                    location=f"cell {cell_index} source",
                    attribute=f"{cell_type}_text",
                    value=source,
                    raw_value=source,
                )
            )
        outputs = cell.get("outputs", [])
        if not isinstance(outputs, list):
            raise ValueError(f"Notebook cell {cell_index} has invalid outputs")
        for output_index, output in enumerate(outputs):
            if not isinstance(output, dict):
                raise ValueError(f"Notebook output {cell_index}:{output_index} is not an object")
            for location, value, _ in _leaf_values(output, f"cell[{cell_index}].output[{output_index}]"):
                evidence.append(
                    Evidence(
                        source_file=path.name,
                        location=location,
                        attribute=location.rsplit(".", 1)[-1].split("[", 1)[0],
                        value=value,
                        raw_value=value,
                    )
                )
    return evidence
