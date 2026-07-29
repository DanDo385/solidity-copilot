#!/usr/bin/env python3
"""Validate Solidity Copilot V1 JSON documents without third-party packages."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "v1"
KINDS = {"candidate-input", "candidate-output", "canonical-record"}
SOLC_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
SAFE_PATH = re.compile(r"^[A-Za-z0-9._/-]+$")


class ValidationError(ValueError):
    pass


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ValidationError(f"cannot read UTF-8 JSON: {exc}") from exc
    try:
        return json.loads(text, object_pairs_hook=reject_duplicate_keys)
    except ValidationError:
        raise
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}") from exc


def resolve_ref(root: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise ValidationError(f"unsupported schema reference: {reference}")
    node: Any = root
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return node


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValidationError(f"unsupported schema type: {expected}")


def validate_schema(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> None:
    if "$ref" in schema:
        validate_schema(value, resolve_ref(root, schema["$ref"]), root, path)
        return
    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: must be one of {schema['enum']!r}")
    expected = schema.get("type")
    if expected and not type_matches(value, expected):
        raise ValidationError(f"{path}: expected {expected}")

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValidationError(f"{path}: missing required property '{key}'")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise ValidationError(f"{path}: unknown property '{unknown[0]}'")
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], root, f"{path}.{key}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"{path}: requires at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                raise ValidationError(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema(item, item_schema, root, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{path}: string is too short")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise ValidationError(f"{path}: does not match required pattern")

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{path}: must be >= {schema['minimum']}")


def ensure_exact_compiler(document: dict[str, Any]) -> None:
    compiler = document.get("compiler")
    if isinstance(compiler, dict):
        version = compiler.get("solc_version")
        if not isinstance(version, str) or SOLC_VERSION.fullmatch(version) is None:
            raise ValidationError("solc_version must be an exact released version such as 0.8.26")


def ensure_safe_path(path: Any, label: str) -> None:
    if not isinstance(path, str) or not path or path.startswith("/") or "\x00" in path:
        raise ValidationError(f"{label}: unsafe repository-relative path")
    if SAFE_PATH.fullmatch(path) is None or any(part == ".." for part in path.split("/")):
        raise ValidationError(f"{label}: unsafe repository-relative path")


def ensure_unique(items: list[dict[str, Any]], key: str, label: str) -> None:
    values = [item.get(key) for item in items if isinstance(item, dict) and key in item]
    if len(values) != len(set(values)):
        duplicate = next(value for value in values if values.count(value) > 1)
        raise ValidationError(f"duplicate {label}: {duplicate}")


def ensure_content_digest(item: dict[str, Any], label: str) -> None:
    if not isinstance(item.get("content"), str) or not isinstance(item.get("content_sha256"), str):
        return
    actual = hashlib.sha256(item["content"].encode("utf-8")).hexdigest()
    if actual != item["content_sha256"]:
        raise ValidationError(f"digest mismatch for {label}")


def task_parts(document: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task = document.get("task")
    if not isinstance(task, dict):
        return [], []
    requirements = task.get("requirements", [])
    invariants = task.get("invariants", [])
    return (
        requirements if isinstance(requirements, list) else [],
        invariants if isinstance(invariants, list) else [],
    )


def validate_task_invariants(document: dict[str, Any]) -> None:
    requirements, invariants = task_parts(document)
    ensure_unique(requirements, "id", "requirement id")
    ensure_unique(invariants, "id", "invariant id")


def content_groups(document: dict[str, Any], canonical: bool) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    for key in ("required_source_files", "reference_context", "public_tests"):
        value = document.get(key, [])
        if isinstance(value, list):
            groups.append((key, value))
    if canonical:
        target = document.get("target", {})
        tests = document.get("tests", {})
        if isinstance(target, dict) and isinstance(target.get("files"), list):
            groups.append(("target.files", target["files"]))
        if isinstance(tests, dict) and isinstance(tests.get("hidden"), list):
            groups.append(("tests.hidden", tests["hidden"]))
    return groups


def validate_content_groups(document: dict[str, Any], canonical: bool) -> list[dict[str, Any]]:
    all_items: list[dict[str, Any]] = []
    for group_name, items in content_groups(document, canonical):
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            ensure_content_digest(item, f"{group_name}[{index}]")
            if "path" in item:
                ensure_safe_path(item["path"], f"{group_name}[{index}].path")
            all_items.append(item)
    ensure_unique(all_items, "artifact_id", "artifact id")
    ensure_unique(all_items, "path", "path")
    return all_items


def validate_candidate_input(document: dict[str, Any]) -> None:
    forbidden = sorted({"target", "tests", "hidden_tests", "security"} & set(document))
    if forbidden:
        raise ValidationError(f"candidate-visible input exposes evaluator-owned field: {forbidden[0]}")
    ensure_exact_compiler(document)
    validate_task_invariants(document)
    validate_content_groups(document, canonical=False)


def validate_candidate_output(document: dict[str, Any]) -> None:
    files = document.get("files", [])
    generated = document.get("generated_tests", [])
    items = []
    if isinstance(files, list):
        items.extend(item for item in files if isinstance(item, dict))
    if isinstance(generated, list):
        items.extend(item for item in generated if isinstance(item, dict))
    for index, item in enumerate(items):
        ensure_safe_path(item.get("path"), f"output[{index}].path")
    paths = [item.get("path") for item in items]
    if len(paths) != len(set(paths)):
        raise ValidationError("duplicate output path across files and generated_tests")
    for item in generated if isinstance(generated, list) else []:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", ""))
        content = str(item.get("content", ""))
        if path.startswith("test/hidden/") or "test/hidden/" in content or "hidden_tests" in content:
            raise ValidationError("generated_tests must not access an evaluator-owned hidden test path")


def validate_license(document: dict[str, Any]) -> None:
    license_data = document.get("license")
    if not isinstance(license_data, dict):
        return
    if license_data.get("review_status") != "approved":
        raise ValidationError("license review must be approved")
    if license_data.get("redistribution_allowed") is not True:
        raise ValidationError("license must allow redistribution")
    if license_data.get("modification_allowed") is not True:
        raise ValidationError("license must allow modification")
    if not str(license_data.get("attribution_notice", "")).strip():
        raise ValidationError("license attribution notice is required")


def validate_required_paths(document: dict[str, Any]) -> None:
    task = document.get("task")
    target = document.get("target")
    if not isinstance(task, dict) or not isinstance(target, dict):
        return
    constraints = task.get("constraints")
    files = target.get("files")
    if not isinstance(constraints, dict) or not isinstance(files, list):
        return
    required = constraints.get("required_target_paths")
    allowed = constraints.get("allowed_output_paths")
    if not isinstance(required, list) or not isinstance(allowed, list):
        return
    target_paths = [item.get("path") for item in files if isinstance(item, dict)]
    if set(required) != set(target_paths):
        raise ValidationError("required target path set must exactly match target.files paths")
    if not set(required).issubset(set(allowed)):
        raise ValidationError("required target path must appear in allowed_output_paths")


def validate_canonical_record(document: dict[str, Any]) -> None:
    ensure_exact_compiler(document)
    validate_license(document)
    validate_task_invariants(document)
    validate_required_paths(document)
    content_items = validate_content_groups(document, canonical=True)

    provenance = document.get("provenance")
    if not isinstance(provenance, dict):
        return
    origin = provenance.get("origin")
    if isinstance(origin, dict):
        revision = origin.get("revision")
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise ValidationError("provenance origin revision must be a full 40-character Git commit SHA")
    artifacts = provenance.get("artifacts", [])
    if not isinstance(artifacts, list):
        return
    ensure_unique(artifacts, "artifact_id", "provenance artifact id")
    ensure_unique(artifacts, "path", "provenance path")
    by_id = {item.get("artifact_id"): item for item in artifacts if isinstance(item, dict)}
    for item in content_items:
        artifact_id = item.get("artifact_id")
        source = by_id.get(artifact_id)
        if source is None:
            raise ValidationError(f"missing immutable provenance for artifact: {artifact_id}")
        if source.get("path") != item.get("path") or source.get("blob_sha256") != item.get("content_sha256"):
            raise ValidationError(f"provenance path or digest mismatch for artifact: {artifact_id}")

    task = document.get("task", {})
    interfaces = task.get("interfaces", []) if isinstance(task, dict) else []
    required_ids = {item.get("artifact_id") for item in document.get("required_source_files", []) if isinstance(item, dict)}
    for interface in interfaces if isinstance(interfaces, list) else []:
        if isinstance(interface, dict) and interface.get("artifact_id") not in required_ids:
            raise ValidationError(f"unresolved interface artifact id: {interface.get('artifact_id')}")

    requirements, invariants = task_parts(document)
    check_ids = {item.get("id") for item in requirements + invariants if isinstance(item, dict)}
    tests = document.get("tests", {})
    if isinstance(tests, dict):
        hidden = tests.get("hidden", [])
        for hidden_test in hidden if isinstance(hidden, list) else []:
            if not isinstance(hidden_test, dict):
                continue
            covers = hidden_test.get("covers", [])
            if not covers or any(test_id not in check_ids for test_id in covers):
                raise ValidationError("hidden test covers must resolve to at least one requirement or invariant")
        required_test_ids = tests.get("required_test_ids", [])
        if isinstance(required_test_ids, list) and any(test_id not in check_ids for test_id in required_test_ids):
            raise ValidationError("required_test_ids contains an unresolved requirement or invariant id")

    target = document.get("target", {})
    references = document.get("reference_context", [])
    target_digests = {item.get("content_sha256") for item in target.get("files", []) if isinstance(target, dict) and isinstance(item, dict)}
    for reference in references if isinstance(references, list) else []:
        if isinstance(reference, dict) and reference.get("content_sha256") in target_digests:
            raise ValidationError("reference context overlaps held-out target content")

    security = document.get("security")
    if isinstance(security, dict):
        artifact_id = security.get("slither_config_artifact_id")
        source = by_id.get(artifact_id)
        if source is None or source.get("blob_sha256") != security.get("slither_config_sha256"):
            raise ValidationError("security configuration lacks matching immutable provenance")


def ensure_container_types(kind: str, document: dict[str, Any]) -> None:
    expected: dict[str, type[Any]] = {}
    if kind == "candidate-input":
        expected = {
            "compiler": dict,
            "task": dict,
            "required_source_files": list,
            "reference_context": list,
            "public_tests": list,
        }
    elif kind == "candidate-output":
        expected = {"files": list, "generated_tests": list, "assumptions": list}
    elif kind == "canonical-record":
        expected = {
            "provenance": dict,
            "license": dict,
            "compiler": dict,
            "task": dict,
            "required_source_files": list,
            "reference_context": list,
            "public_tests": list,
            "target": dict,
            "tests": dict,
            "security": dict,
        }
    for key, container_type in expected.items():
        if key in document and not isinstance(document[key], container_type):
            raise ValidationError(f"$.{key}: expected {container_type.__name__.replace('dict', 'object').replace('list', 'array')}")


def validate(kind: str, document: Any) -> None:
    if not isinstance(document, dict):
        raise ValidationError("document root must be a JSON object")
    ensure_container_types(kind, document)
    if kind == "candidate-input":
        validate_candidate_input(document)
    elif kind == "candidate-output":
        validate_candidate_output(document)
    elif kind == "canonical-record":
        validate_canonical_record(document)
    schema = read_json(SCHEMA_DIR / f"{kind}.schema.json")
    validate_schema(document, schema, schema)


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in KINDS:
        kinds = "|".join(sorted(KINDS))
        print(f"usage: {Path(argv[0]).name} <{kinds}> <document.json>", file=sys.stderr)
        return 2
    try:
        document = read_json(Path(argv[2]))
        validate(argv[1], document)
    except ValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 1
    print("valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
