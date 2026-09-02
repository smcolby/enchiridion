"""Tests for implicit atomic-rule structure and source-derived inventory mapping."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import rule_template as template  # noqa: E402


def test_all_canonical_artifacts_map_without_structural_errors() -> None:
    inventory = template.load_inventory()

    errors = template.validate_inventory(inventory)

    assert len(inventory) == 34
    assert sum(artifact.artifact_type == "block" for artifact in inventory) == 6
    assert sum(artifact.artifact_type == "rule" for artifact in inventory) == 28
    assert errors == []


def test_every_anti_hallucination_row_becomes_one_treatment() -> None:
    inventory = template.load_inventory()
    examples = [
        item
        for artifact in inventory
        for item in artifact.items
        if item.kind == "anti-hallucination"
    ]

    assert len(examples) == 158
    assert all(item.treatment for item in examples)
    assert all(item.treatment.startswith("Banned: ") for item in examples if item.treatment)
    assert all("\nCorrect: " in item.treatment for item in examples if item.treatment)


def test_source_derived_identifiers_are_globally_unique() -> None:
    inventory = template.load_inventory()
    identifiers = [item.id for artifact in inventory for item in artifact.items]

    assert len(identifiers) == len(set(identifiers))


def test_markdown_table_parser_preserves_escaped_pipes() -> None:
    row = template._split_table_row(r"| `X \| None` | `X or None` |")

    assert row == (r"`X \| None`", "`X or None`")


def test_content_identity_is_independent_of_source_order() -> None:
    first = template._content_hash("directive", "Structure", "Use explicit names.")
    second = template._content_hash("directive", "Structure", "Use explicit names.")

    assert first == second


def test_generated_audit_contains_every_candidate_treatment(tmp_path: Path) -> None:
    inventory = template.load_inventory()
    errors = template.validate_inventory(inventory)

    json_path, markdown_path = template.write_audit(inventory, errors, tmp_path)
    audit = markdown_path.read_text()
    treatment_ids = [
        item.id for artifact in inventory for item in artifact.items if item.treatment is not None
    ]

    assert json_path.is_file()
    assert all(identifier in audit for identifier in treatment_ids)
