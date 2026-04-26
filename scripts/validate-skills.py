#!/usr/bin/env python3
"""Validate SKILL.md frontmatter and plugin/marketplace JSON files.

Usage:
    python3 scripts/validate-skills.py [--root PATH]

Exits with status 1 if any validation error is found.

Requires:
    - python-frontmatter
    - jsonschema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import frontmatter
from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

# Frontmatter schema for SKILL.md.
SKILL_FRONTMATTER_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Claude Code SKILL.md frontmatter",
    "type": "object",
    "required": ["description"],
    "additionalProperties": False,
    "properties": {
        "description": {"type": "string", "minLength": 1},
        "allowed-tools": {"type": "string"},
        "disable-model-invocation": {"type": "boolean"},
    },
}

SKILL_GLOBS = ["plugins/**/SKILL.md", "template/SKILL.md"]
PLUGIN_JSON_GLOB = "plugins/*/.claude-plugin/plugin.json"
MARKETPLACE_JSON_PATH = ".claude-plugin/marketplace.json"


class ValidationReport:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.checked_files = 0

    def _format_path(self, file: Path) -> str:
        try:
            return str(file.relative_to(self.root))
        except ValueError:
            return str(file)

    def error(self, file: Path, message: str) -> None:
        self.errors.append(f"ERROR  {self._format_path(file)}: {message}")

    def has_errors(self) -> bool:
        return bool(self.errors)


def validate_against(
    file: Path,
    data: Any,
    validator: Draft202012Validator,
    report: ValidationReport,
) -> None:
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in err.absolute_path) or "<root>"
        report.error(file, f"{path}: {err.message}")


def validate_skill_files(
    root: Path, validator: Draft202012Validator, report: ValidationReport
) -> None:
    for pattern in SKILL_GLOBS:
        for path in sorted(root.glob(pattern)):
            if path.name.endswith(".local.md"):
                continue
            report.checked_files += 1
            try:
                post = frontmatter.load(str(path))
            except Exception as exc:
                report.error(path, f"frontmatter parse error: {exc}")
                continue
            if not post.metadata:
                report.error(path, "missing or empty YAML frontmatter")
                continue
            validate_against(path, post.metadata, validator, report)


def load_json(path: Path, report: ValidationReport) -> Any | None:
    report.checked_files += 1
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        report.error(path, f"cannot read file: {exc}")
    except json.JSONDecodeError as exc:
        report.error(path, f"JSON parse error: {exc}")
    return None


def validate_json_files(
    root: Path, validator: Draft202012Validator, glob: str, report: ValidationReport
) -> None:
    for path in sorted(root.glob(glob)):
        data = load_json(path, report)
        if data is not None:
            validate_against(path, data, validator, report)


def load_schema(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root (default: auto-detect)")
    args = parser.parse_args()
    root: Path = args.root.resolve()

    report = ValidationReport(root)
    skill_validator = Draft202012Validator(SKILL_FRONTMATTER_SCHEMA)
    plugin_validator = load_schema(SCHEMAS_DIR / "plugin.schema.json")
    marketplace_validator = load_schema(SCHEMAS_DIR / "marketplace.schema.json")

    validate_skill_files(root, skill_validator, report)
    validate_json_files(root, plugin_validator, PLUGIN_JSON_GLOB, report)

    marketplace_path = root / MARKETPLACE_JSON_PATH
    if marketplace_path.exists():
        data = load_json(marketplace_path, report)
        if data is not None:
            validate_against(marketplace_path, data, marketplace_validator, report)
    else:
        report.error(marketplace_path, "marketplace.json not found")
        report.checked_files += 1

    for line in report.errors:
        print(line, file=sys.stderr)
    print(f"\nChecked {report.checked_files} file(s): {len(report.errors)} error(s)")
    return 1 if report.has_errors() else 0


if __name__ == "__main__":
    sys.exit(main())
