import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "validate_v1.py"
FIXTURES = ROOT / "tests" / "fixtures" / "v1"
SCHEMAS = ROOT / "schemas" / "v1"


def run_validator(kind: str, fixture: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), kind, str(fixture)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


class V1ValidatorTests(unittest.TestCase):
    def test_versioned_schemas_exist_and_are_json_schema_2020_12(self):
        import json

        for name in ("candidate-input", "candidate-output", "canonical-record"):
            path = SCHEMAS / f"{name}.schema.json"
            self.assertTrue(path.is_file(), path)
            schema = json.loads(path.read_text())
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertEqual(schema["$id"], f"https://solidity-copilot.invalid/schemas/v1/{name}.schema.json")

    def test_all_valid_synthetic_fixtures_are_accepted(self):
        for kind in ("candidate-input", "candidate-output", "canonical-record"):
            with self.subTest(kind=kind):
                result = run_validator(kind, FIXTURES / "valid" / f"{kind}.json")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "valid")

    def test_invalid_fixtures_are_rejected_for_the_expected_rule(self):
        cases = {
            "canonical-missing-provenance.json": ("canonical-record", "provenance"),
            "canonical-duplicate-identifiers.json": ("canonical-record", "duplicate requirement id"),
            "canonical-bad-digest.json": ("canonical-record", "digest mismatch"),
            "canonical-unpinned-compiler.json": ("canonical-record", "solc_version"),
            "canonical-license-unapproved.json": ("canonical-record", "license review"),
            "canonical-required-path-mismatch.json": ("canonical-record", "required target path"),
            "candidate-input-hidden-test-leak.json": ("candidate-input", "hidden_tests"),
            "candidate-output-hidden-test-path.json": ("candidate-output", "hidden test path"),
            "candidate-output-duplicate-path.json": ("candidate-output", "duplicate output path"),
            "candidate-output-duplicate-key.json": ("candidate-output", "duplicate json key"),
        }
        for filename, (kind, message) in cases.items():
            with self.subTest(filename=filename):
                result = run_validator(kind, FIXTURES / "invalid" / filename)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(message, result.stderr.lower())

    def test_malformed_structure_is_reported_without_traceback(self):
        result = run_validator(
            "canonical-record",
            FIXTURES / "invalid" / "canonical-target-not-object.json",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("expected object", result.stderr.lower())
        self.assertNotIn("traceback", result.stderr.lower())

    def test_unknown_document_kind_is_usage_error(self):
        result = run_validator("mystery", FIXTURES / "valid" / "candidate-input.json")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
