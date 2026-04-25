#!/usr/bin/env python3
"""Validate SKILL.md frontmatter and plugin/marketplace JSON files.

Usage:
    python3 scripts/validate-skills.py [--root PATH]

Exits with status 1 if any validation error is found.

Requires PyYAML (`pip install pyyaml`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Frontmatter schema for SKILL.md (and template/SKILL.md).
SKILL_REQUIRED_FIELDS = {"description"}
SKILL_OPTIONAL_FIELDS = {"allowed-tools", "disable-model-invocation"}
SKILL_KNOWN_FIELDS = SKILL_REQUIRED_FIELDS | SKILL_OPTIONAL_FIELDS

# Patterns to validate.
SKILL_GLOBS = ["plugins/**/SKILL.md", "template/SKILL.md"]
PLUGIN_JSON_GLOB = "plugins/*/.claude-plugin/plugin.json"
MARKETPLACE_JSON_PATH = ".claude-plugin/marketplace.json"


class ValidationReport:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checked_files = 0

    def _format_path(self, file: Path) -> str:
        try:
            return str(file.relative_to(self.root))
        except ValueError:
            return str(file)

    def error(self, file: Path, message: str) -> None:
        self.errors.append(f"ERROR  {self._format_path(file)}: {message}")

    def warn(self, file: Path, message: str) -> None:
        self.warnings.append(f"WARN   {self._format_path(file)}: {message}")

    def has_errors(self) -> bool:
        return bool(self.errors)


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str | None]:
    """Extract and parse the YAML frontmatter block at the start of the file.

    Returns (parsed_dict, error_message). Exactly one of the two is None.
    """
    if not content.startswith("---\n") and not content.startswith("---\r\n"):
        return None, "missing opening '---' delimiter for frontmatter"

    # Strip the leading delimiter line.
    body = content.split("\n", 1)[1] if content.startswith("---\n") else content.split("\r\n", 1)[1]

    closing_idx = body.find("\n---\n")
    if closing_idx == -1:
        # Allow EOF after closing delimiter.
        if body.rstrip().endswith("---"):
            closing_idx = body.rstrip().rfind("---")
            yaml_block = body[:closing_idx]
        else:
            return None, "missing closing '---' delimiter for frontmatter"
    else:
        yaml_block = body[:closing_idx]

    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"

    if parsed is None:
        return None, "frontmatter block is empty"
    if not isinstance(parsed, dict):
        return None, f"frontmatter must be a mapping, got {type(parsed).__name__}"

    return parsed, None


def validate_skill_frontmatter(file: Path, fm: dict[str, Any], report: ValidationReport) -> None:
    # Required fields.
    for field in SKILL_REQUIRED_FIELDS:
        if field not in fm:
            report.error(file, f"missing required frontmatter field: '{field}'")

    # Field types.
    if "description" in fm:
        value = fm["description"]
        if not isinstance(value, str):
            report.error(file, f"'description' must be a string, got {type(value).__name__}")
        elif not value.strip():
            report.error(file, "'description' must not be empty")

    if "allowed-tools" in fm:
        value = fm["allowed-tools"]
        if not isinstance(value, str):
            report.error(file, f"'allowed-tools' must be a string, got {type(value).__name__}")

    if "disable-model-invocation" in fm:
        value = fm["disable-model-invocation"]
        if not isinstance(value, bool):
            report.error(file, f"'disable-model-invocation' must be a boolean, got {type(value).__name__}")

    # Unknown fields → warn (don't fail).
    for field in fm:
        if field not in SKILL_KNOWN_FIELDS:
            report.warn(file, f"unknown frontmatter field: '{field}'")


def validate_skill_files(root: Path, report: ValidationReport) -> None:
    for pattern in SKILL_GLOBS:
        for path in sorted(root.glob(pattern)):
            # Skip *.local.md variants — not validated.
            if path.name.endswith(".local.md"):
                continue
            report.checked_files += 1
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                report.error(path, f"cannot read file: {exc}")
                continue

            fm, err = parse_frontmatter(content)
            if err is not None:
                report.error(path, err)
                continue
            assert fm is not None
            validate_skill_frontmatter(path, fm, report)


def validate_json_file(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    report.checked_files += 1
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        report.error(path, f"cannot read file: {exc}")
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        report.error(path, f"JSON parse error: {exc}")
        return None


def validate_plugin_jsons(root: Path, report: ValidationReport) -> None:
    for path in sorted(root.glob(PLUGIN_JSON_GLOB)):
        data = validate_json_file(path, report)
        if data is None:
            continue
        if not isinstance(data, dict):
            report.error(path, "plugin.json must be a JSON object")
            continue
        for required in ("name", "description", "version"):
            if required not in data:
                report.error(path, f"missing required field: '{required}'")


def validate_marketplace_json(root: Path, report: ValidationReport) -> None:
    path = root / MARKETPLACE_JSON_PATH
    if not path.exists():
        report.error(path, "marketplace.json not found")
        return
    data = validate_json_file(path, report)
    if data is None:
        return
    if not isinstance(data, dict):
        report.error(path, "marketplace.json must be a JSON object")
        return
    if "plugins" not in data:
        report.error(path, "missing required field: 'plugins'")
        return
    if not isinstance(data["plugins"], list):
        report.error(path, "'plugins' must be an array")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="Repository root (default: auto-detect)")
    args = parser.parse_args()
    root: Path = args.root.resolve()

    report = ValidationReport(root)
    validate_skill_files(root, report)
    validate_plugin_jsons(root, report)
    validate_marketplace_json(root, report)

    for line in report.warnings:
        print(line)
    for line in report.errors:
        print(line, file=sys.stderr)

    print(
        f"\nChecked {report.checked_files} file(s): "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    return 1 if report.has_errors() else 0


if __name__ == "__main__":
    sys.exit(main())
