"""Tests for native rule rendering and tier-based activation."""

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import render_rules  # noqa: E402

FORMATS = ("mdc", "copilot", "claude")


def _write_rule(tmp_path: Path, tier: str) -> Path:
    """Write a minimal canonical rule with broad Python scope."""
    rule_path = tmp_path / f"{tier}-rule.md"
    rule_path.write_text(
        f"""---
name: {tier}-rule
description: Apply when the named package is used.
tier: {tier}
scope: ["**/*.py"]
stack: []
---

Apply the package-specific guidance.
"""
    )
    return rule_path


@pytest.mark.parametrize("fmt", FORMATS)
def test_requested_rules_require_explicit_native_render_opt_in(tmp_path: Path, fmt: str) -> None:
    # Arrange a requested rule whose path scope would match every Python file
    rule_path = _write_rule(tmp_path, "requested")

    # Render without accepting project-wide activation
    rendered = render_rules.render(rule_path, fmt, include_provenance=False)

    # Requested rules remain routed through the rules skill
    assert rendered is None


@pytest.mark.parametrize(
    ("fmt", "scope_render"),
    [
        ("mdc", "globs: '**/*.py'"),
        ("copilot", "applyTo: '**/*.py'"),
        ("claude", "paths:\n- '**/*.py'"),
    ],
)
def test_include_requested_renders_requested_rule(
    tmp_path: Path, fmt: str, scope_render: str
) -> None:
    # Arrange a requested rule selected for explicit native deployment
    rule_path = _write_rule(tmp_path, "requested")

    # Render after accepting its broad path scope
    rendered = render_rules.render(
        rule_path,
        fmt,
        include_provenance=False,
        include_requested=True,
    )

    # Every native format receives the requested rule and its declared scope
    assert rendered is not None
    filename, content = rendered
    assert filename.startswith("requested-rule.")
    assert scope_render in content
    assert "Apply the package-specific guidance." in content


@pytest.mark.parametrize("fmt", FORMATS)
def test_invoked_rules_have_no_native_rendering(tmp_path: Path, fmt: str) -> None:
    # Arrange a rule reserved for explicit playbook or user invocation
    rule_path = _write_rule(tmp_path, "invoked")

    # Try both default and requested-rule opt-in rendering
    default_render = render_rules.render(rule_path, fmt, include_provenance=False)
    requested_render = render_rules.render(
        rule_path,
        fmt,
        include_provenance=False,
        include_requested=True,
    )

    # The requested-rule switch never broadens invoked-rule activation
    assert default_render is None
    assert requested_render is None


@pytest.mark.parametrize("fmt", FORMATS)
def test_scoped_rules_render_without_opt_in(tmp_path: Path, fmt: str) -> None:
    # Arrange a path-activated rule
    rule_path = _write_rule(tmp_path, "scoped")

    # Render with default tier handling
    rendered = render_rules.render(rule_path, fmt, include_provenance=False)

    # Scoped rules retain native path rendering
    assert rendered is not None
