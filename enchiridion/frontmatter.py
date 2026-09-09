"""Parse YAML frontmatter shared by rules, skills, and agents."""

import re
from typing import Any

import yaml

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load_frontmatter(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse a frontmatter YAML block into a mapping or an error message.

    Parameters
    ----------
    raw : str
        YAML text between frontmatter delimiters.

    Returns
    -------
    tuple of (dict or None, str or None)
        Parsed mapping and no error, or no mapping and an actionable error.
    """
    try:
        value = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        detail = str(error).replace("\n", " ")
        hint = (
            " (a value containing a colon followed by a space must be quoted,"
            ' e.g. description: "foo: bar")'
        )
        return None, f"invalid YAML frontmatter: {detail}{hint}"
    if not isinstance(value, dict):
        return None, "frontmatter is not a mapping"
    return value, None
