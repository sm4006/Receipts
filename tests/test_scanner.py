import json
import tempfile
import unittest
from pathlib import Path

from receipts.scanner import scan_project


class ScannerTests(unittest.TestCase):
    def write_file(self, root: Path, name: str, content: str) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_readme_evidence_preserves_documentation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = "# Results\nAccuracy: 91.8%\n"
            self.write_file(root, "README.md", text)
            result = scan_project(root)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(result.evidence[0].source_file, "README.md")
            self.assertEqual(result.evidence[0].location, "document")
            self.assertEqual(result.evidence[0].value, text)
            self.assertEqual(result.evidence[0].raw_value, text)

    def test_csv_evidence_has_columns_values_and_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "metrics.csv", "accuracy,epochs\n91.8,12\n")
            result = scan_project(root)
            self.assertEqual(len(result.errors), 0)
            self.assertEqual(
                [(item.attribute, item.value, item.location) for item in result.evidence],
                [
                    ("accuracy", "91.8", "row 2, column accuracy"),
                    ("epochs", "12", "row 2, column epochs"),
                ],
            )

    def test_json_evidence_traverses_nested_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "metrics.json", json.dumps({"metrics": {"acc": 0.918}, "rows": [10, 20]}))
            result = scan_project(root)
            self.assertEqual(len(result.errors), 0)
            values = {(item.attribute, item.location, item.value) for item in result.evidence}
            self.assertIn(("acc", "$.metrics.acc", 0.918), values)
            self.assertIn(("rows", "$.rows[0]", 10), values)

    def test_ipynb_is_read_as_json_without_executing_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "executed.txt"
            code = f"Path({str(marker)!r}).write_text('executed')"
            notebook = {
                "cells": [{"cell_type": "code", "source": [code], "outputs": [{"data": {"text/plain": ["12"]}}]}],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            self.write_file(root, "analysis.ipynb", json.dumps(notebook))
            result = scan_project(root)
            self.assertEqual(len(result.errors), 0)
            self.assertFalse(marker.exists())
            self.assertTrue(any(item.value == code for item in result.evidence))
            self.assertTrue(any(item.value == "12" for item in result.evidence))

    def test_malformed_files_are_reported_without_stopping_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "bad.json", "{")
            self.write_file(root, "bad.csv", "accuracy,epochs\n91.8\n")
            self.write_file(root, "good.json", '{"accuracy": 91.8}')
            result = scan_project(root)
            self.assertEqual(len(result.errors), 2)
            self.assertTrue(any(item.value == 91.8 for item in result.evidence))

    def test_malformed_notebook_structure_is_reported_without_crashing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "bad.ipynb", "[]")
            self.write_file(root, "good.json", '{"accuracy": 91.8}')
            result = scan_project(root)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("Notebook must be a JSON object", result.errors[0])
            self.assertTrue(any(item.value == 91.8 for item in result.evidence))

    def test_notebook_source_parts_must_be_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            notebook = {"cells": [{"cell_type": "code", "source": ["accuracy = ", 91.8]}]}
            self.write_file(root, "bad.ipynb", json.dumps(notebook))
            result = scan_project(root)
            self.assertEqual(len(result.errors), 1)
            self.assertIn("invalid source", result.errors[0])

    def test_unsupported_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "script.py", "raise RuntimeError('must not run')")
            self.write_file(root, "notes.txt", "not supported")
            result = scan_project(root)
            self.assertEqual(result.evidence, [])
            self.assertEqual(result.errors, [])
            self.assertEqual(result.files, [])

    def test_nested_source_file_provenance_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_file(root, "data/results.csv", "acc\n91.80%\n")
            result = scan_project(root)
            item = result.evidence[0]
            self.assertEqual(item.source_file, "data\\results.csv")
            self.assertEqual(item.location, "row 2, column acc")
            self.assertEqual(item.raw_value, "91.80%")


if __name__ == "__main__":
    unittest.main()
