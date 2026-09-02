#!/usr/bin/env python3
"""Validate and inventory canonical doctrine and rule Markdown structure.

The parser derives stable identifiers and exact candidate treatments from source
files without maintaining copied instruction text. Generated audit artifacts are
ignored by git and can be recreated at any time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent
BLOCKS_DIR = REPO / "shared/blocks"
RULES_DIR = REPO / "shared/rules"
ARTIFACTS_DIR = REPO / ".counterfactual-artifacts"
FRONTMATTER_RE = re.compile(r"^---\n(?P<frontmatter>.*?)\n---\n", re.DOTALL)
HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<title>.+?)\s*$")
LIST_ITEM_RE = re.compile(r"^(?P<marker>-|\d+\.)\s+(?P<text>.+)$")
TABLE_SEPARATOR_RE = re.compile(r"^:?-{3,}:?$")
WORD_RE = re.compile(r"[a-z0-9]+")
REFERENCE_SECTIONS = {"reference", "references", "reference exemplar", "see also"}
DIRECTIVE_PROSE_SECTIONS = {"banned vocabulary"}
COMPOUND_CUE_RE = re.compile(
    r"(?:^|[.;!?]\s+)(?:do not|never|avoid|prefer|require|validate|report|state|write|"
    r"keep|use|run|preserve|define|catch|log|document|treat|ensure|reject|store)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceItem:
    """Represent one structurally derived source item and candidate treatment."""

    id: str
    artifact: str
    path: str
    section: str
    kind: str
    line_start: int
    line_end: int
    text: str
    treatment: str | None
    content_hash: str
    compound_candidate: bool


@dataclass(frozen=True)
class ArtifactInventory:
    """Collect parsed items and validation errors for one canonical artifact."""

    name: str
    path: str
    artifact_type: str
    items: tuple[SourceItem, ...]
    errors: tuple[str, ...]


@dataclass(frozen=True)
class ParsedBlock:
    """Represent one Markdown paragraph, list item, table, or heading."""

    kind: str
    line_start: int
    line_end: int
    text: str
    marker: str | None = None
    heading_level: int | None = None
    heading_title: str | None = None
    rows: tuple[tuple[str, ...], ...] = ()


def _normalize_space(text: str) -> str:
    """Collapse Markdown wrapping while preserving the authored token sequence."""
    return " ".join(text.split())


def _plain_text(text: str) -> str:
    """Remove common Markdown punctuation for readable identifier slugs."""
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", plain)
    plain = plain.replace("`", "").replace("*", "")
    return _normalize_space(plain).lower()


def _slug(text: str, maximum_words: int = 9) -> str:
    """Derive a compact lowercase slug from source text."""
    words = WORD_RE.findall(_plain_text(text))[:maximum_words]
    return "-".join(words) or "item"


def _content_hash(kind: str, section: str, text: str) -> str:
    """Hash semantic location and normalized content for cache-safe identity."""
    payload = f"{kind}\n{_normalize_space(section)}\n{_normalize_space(text)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


def _split_table_row(line: str) -> tuple[str, ...]:
    """Split a Markdown table row while preserving escaped pipe characters."""
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise ValueError("table rows must start and end with a pipe")

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for character in stripped[1:-1]:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            current.append(character)
            escaped = True
        elif character == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(character)
    cells.append("".join(current).strip())
    return tuple(cells)


def _parse_markdown_blocks(text: str, line_offset: int = 0) -> tuple[ParsedBlock, ...]:
    """Parse the limited Markdown structures used by canonical rule artifacts."""
    lines = text.splitlines()
    blocks: list[ParsedBlock] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        line_number = line_offset + index + 1
        if not line.strip():
            index += 1
            continue

        heading = HEADING_RE.match(line)
        if heading:
            blocks.append(
                ParsedBlock(
                    kind="heading",
                    line_start=line_number,
                    line_end=line_number,
                    text=heading.group("title"),
                    heading_level=len(heading.group("marks")),
                    heading_title=heading.group("title"),
                )
            )
            index += 1
            continue

        list_item = LIST_ITEM_RE.match(line)
        if list_item:
            collected = [list_item.group("text")]
            end = index
            while end + 1 < len(lines):
                candidate = lines[end + 1]
                if not candidate.strip():
                    break
                if HEADING_RE.match(candidate) or LIST_ITEM_RE.match(candidate):
                    break
                if candidate.startswith("|"):
                    break
                collected.append(candidate.strip())
                end += 1
            blocks.append(
                ParsedBlock(
                    kind="list",
                    line_start=line_number,
                    line_end=line_offset + end + 1,
                    text=_normalize_space(" ".join(collected)),
                    marker=list_item.group("marker"),
                )
            )
            index = end + 1
            continue

        if line.startswith("|"):
            rows: list[tuple[str, ...]] = []
            end = index
            while end < len(lines) and lines[end].startswith("|"):
                rows.append(_split_table_row(lines[end]))
                end += 1
            blocks.append(
                ParsedBlock(
                    kind="table",
                    line_start=line_number,
                    line_end=line_offset + end,
                    text="\n".join(lines[index:end]),
                    rows=tuple(rows),
                )
            )
            index = end
            continue

        collected = [line.strip()]
        end = index
        while end + 1 < len(lines):
            candidate = lines[end + 1]
            if not candidate.strip():
                break
            if HEADING_RE.match(candidate) or LIST_ITEM_RE.match(candidate):
                break
            if candidate.startswith("|"):
                break
            collected.append(candidate.strip())
            end += 1
        blocks.append(
            ParsedBlock(
                kind="paragraph",
                line_start=line_number,
                line_end=line_offset + end + 1,
                text=_normalize_space(" ".join(collected)),
            )
        )
        index = end + 1
    return tuple(blocks)


def _section_kind(section: str, block_kind: str, marker: str | None) -> str:
    """Classify content from its implicit heading and list structure."""
    normalized = section.lower()
    if normalized == "principles" and marker and marker != "-":
        return "principle"
    if normalized in {"scope", "scope of application"}:
        return "scope"
    if normalized == "enforcement":
        return "enforcement"
    if normalized in REFERENCE_SECTIONS:
        return "reference"
    if block_kind == "paragraph" and normalized not in DIRECTIVE_PROSE_SECTIONS:
        return "context"
    return "directive"


def _is_compound_candidate(text: str, kind: str) -> bool:
    """Flag directives with several imperative cues for manual atomicity review."""
    if kind not in {"directive", "principle", "scope"}:
        return False
    cues = COMPOUND_CUE_RE.findall(text)
    return len(cues) >= 2


def _make_item(
    artifact: str,
    path: Path,
    section: str,
    kind: str,
    line_start: int,
    line_end: int,
    text: str,
    treatment: str | None,
) -> SourceItem:
    """Build one content-addressed source item from canonical text."""
    digest = _content_hash(kind, section, text)
    item_id = f"{artifact}.{_slug(section)}.{_slug(text)}-{digest}"
    return SourceItem(
        id=item_id,
        artifact=artifact,
        path=str(path.relative_to(REPO)),
        section=section,
        kind=kind,
        line_start=line_start,
        line_end=line_end,
        text=text,
        treatment=treatment,
        content_hash=digest,
        compound_candidate=_is_compound_candidate(text, kind),
    )


def _parse_rule(path: Path) -> ArtifactInventory:
    """Parse one complete rule with frontmatter and H2 sections."""
    raw = path.read_text()
    match = FRONTMATTER_RE.match(raw)
    errors: list[str] = []
    if not match:
        return ArtifactInventory(
            name=path.stem,
            path=str(path.relative_to(REPO)),
            artifact_type="rule",
            items=(),
            errors=("missing YAML frontmatter",),
        )
    try:
        frontmatter = yaml.safe_load(match.group("frontmatter"))
    except yaml.YAMLError as error:
        return ArtifactInventory(
            name=path.stem,
            path=str(path.relative_to(REPO)),
            artifact_type="rule",
            items=(),
            errors=(f"invalid YAML frontmatter: {error}",),
        )
    if not isinstance(frontmatter, dict) or not isinstance(frontmatter.get("name"), str):
        return ArtifactInventory(
            name=path.stem,
            path=str(path.relative_to(REPO)),
            artifact_type="rule",
            items=(),
            errors=("frontmatter requires a string name",),
        )

    artifact = frontmatter["name"]
    body = raw[match.end() :]
    line_offset = raw[: match.end()].count("\n")
    blocks = _parse_markdown_blocks(body, line_offset=line_offset)
    items: list[SourceItem] = []
    section = "role"
    seen_heading = False
    for block in blocks:
        if block.kind == "heading":
            seen_heading = True
            if block.heading_level != 2:
                errors.append(
                    f"line {block.line_start}: rule headings must use H2, "
                    f"found H{block.heading_level}"
                )
            section = block.heading_title or "untitled"
            continue

        if block.kind == "table":
            if section.lower() != "anti-hallucination":
                errors.append(f"line {block.line_start}: table outside Anti-hallucination")
                continue
            table_items, table_errors = _parse_anti_table(artifact, path, section, block)
            items.extend(table_items)
            errors.extend(table_errors)
            continue

        if section.lower() == "anti-hallucination":
            errors.append(
                f"line {block.line_start}: Anti-hallucination accepts only Banned/Correct tables"
            )
            continue

        if not seen_heading:
            kind = "role"
        else:
            kind = _section_kind(section, block.kind, block.marker)
        treatment = block.text if kind not in {"context", "reference", "enforcement"} else None
        items.append(
            _make_item(
                artifact,
                path,
                section,
                kind,
                block.line_start,
                block.line_end,
                block.text,
                treatment,
            )
        )

    return ArtifactInventory(
        name=artifact,
        path=str(path.relative_to(REPO)),
        artifact_type="rule",
        items=tuple(items),
        errors=tuple(errors),
    )


def _parse_anti_table(
    artifact: str,
    path: Path,
    section: str,
    block: ParsedBlock,
) -> tuple[list[SourceItem], list[str]]:
    """Parse one canonical two-column anti-hallucination table."""
    errors: list[str] = []
    if len(block.rows) < 2:
        return [], [f"line {block.line_start}: anti-hallucination table has no header"]
    header = tuple(_plain_text(cell) for cell in block.rows[0])
    if header != ("banned", "correct"):
        errors.append(
            f"line {block.line_start}: anti-hallucination header must be Banned | Correct"
        )
    separator = block.rows[1]
    if len(separator) != 2 or not all(TABLE_SEPARATOR_RE.fullmatch(cell) for cell in separator):
        errors.append(f"line {block.line_start + 1}: malformed table separator")

    items: list[SourceItem] = []
    for index, row in enumerate(block.rows[2:], start=2):
        line_number = block.line_start + index
        if len(row) != 2 or not all(cell.strip() for cell in row):
            errors.append(
                f"line {line_number}: anti-hallucination rows require two non-empty cells"
            )
            continue
        banned, correct = row
        source_text = f"{banned} => {correct}"
        treatment = f"Banned: {banned}\nCorrect: {correct}"
        items.append(
            _make_item(
                artifact,
                path,
                section,
                "anti-hallucination",
                line_number,
                line_number,
                source_text,
                treatment,
            )
        )
    return items, errors


def _parse_block(path: Path) -> ArtifactInventory:
    """Parse one frontmatter-free doctrine fragment."""
    items: list[SourceItem] = []
    errors: list[str] = []
    artifact = path.stem
    section = "directives"
    for block in _parse_markdown_blocks(path.read_text()):
        if block.kind == "heading":
            section = block.heading_title or "directives"
            continue
        if block.kind == "table":
            errors.append(f"line {block.line_start}: doctrine blocks do not support tables")
            continue
        items.append(
            _make_item(
                artifact,
                path,
                section,
                "directive",
                block.line_start,
                block.line_end,
                block.text,
                block.text,
            )
        )
    return ArtifactInventory(
        name=artifact,
        path=str(path.relative_to(REPO)),
        artifact_type="block",
        items=tuple(items),
        errors=tuple(errors),
    )


def load_inventory() -> tuple[ArtifactInventory, ...]:
    """Parse every canonical doctrine block and rule artifact."""
    artifacts = [_parse_block(path) for path in sorted(BLOCKS_DIR.glob("*.md"))]
    artifacts.extend(_parse_rule(path) for path in sorted(RULES_DIR.rglob("*.md")))
    return tuple(artifacts)


def render_rule_treatment(
    artifact: ArtifactInventory, omitted_item_ids: tuple[str, ...] = ()
) -> str:
    """Render one canonical rule body with selected source items omitted."""
    if artifact.artifact_type != "rule":
        raise ValueError(f"cannot render non-rule artifact '{artifact.path}'")
    item_by_id = {item.id: item for item in artifact.items}
    unknown = sorted(set(omitted_item_ids) - set(item_by_id))
    if unknown:
        raise ValueError(f"unknown source items for '{artifact.path}': {', '.join(unknown)}")

    # Mark exact source lines for atomic omissions
    omitted = set(omitted_item_ids)
    removed_lines = {
        line_number
        for item_id in omitted
        for line_number in range(
            item_by_id[item_id].line_start,
            item_by_id[item_id].line_end + 1,
        )
    }
    path = REPO / artifact.path
    raw = path.read_text()
    frontmatter = FRONTMATTER_RE.match(raw)
    if frontmatter is None:
        raise ValueError(f"rule has no frontmatter: {artifact.path}")
    lines = raw.splitlines()
    body_start = raw[: frontmatter.end()].count("\n")

    # Remove headings and structural table lines when a whole section becomes empty
    section_items: dict[str, set[str]] = {}
    for item in artifact.items:
        if item.section == "role":
            continue
        section_items.setdefault(item.section, set()).add(item.id)
    headings = [
        (index, match.group("title"))
        for index, line in enumerate(lines)
        if (match := HEADING_RE.match(line)) and len(match.group("marks")) == 2
    ]
    for heading_index, (line_index, title) in enumerate(headings):
        item_ids = section_items.get(title, set())
        if not item_ids or not item_ids.issubset(omitted):
            continue
        end_index = (
            headings[heading_index + 1][0] if heading_index + 1 < len(headings) else len(lines)
        )
        removed_lines.update(range(line_index + 1, end_index + 1))

    # Keep canonical wording and Markdown unchanged outside omitted line ranges
    rendered_lines = [
        line
        for line_number, line in enumerate(lines[body_start:], start=body_start + 1)
        if line_number not in removed_lines
    ]
    rendered = "\n".join(rendered_lines).strip()
    return re.sub(r"\n{3,}", "\n\n", rendered)


def validate_inventory(inventory: tuple[ArtifactInventory, ...]) -> list[str]:
    """Return structural and global-identity errors for a parsed inventory."""
    errors = [f"{artifact.path}: {error}" for artifact in inventory for error in artifact.errors]
    seen: dict[str, SourceItem] = {}
    for artifact in inventory:
        if not artifact.items:
            errors.append(f"{artifact.path}: no source items parsed")
        for item in artifact.items:
            previous = seen.get(item.id)
            if previous:
                errors.append(
                    f"{item.path}:{item.line_start}: duplicate id {item.id} "
                    f"(also {previous.path}:{previous.line_start})"
                )
            seen[item.id] = item
    return errors


def _summary(inventory: tuple[ArtifactInventory, ...]) -> Counter[str]:
    """Count artifacts, parsed kinds, treatments, and compound candidates."""
    counts: Counter[str] = Counter()
    counts["artifacts"] = len(inventory)
    for artifact in inventory:
        counts[f"artifact:{artifact.artifact_type}"] += 1
        for item in artifact.items:
            counts[f"kind:{item.kind}"] += 1
            counts["items"] += 1
            counts["treatments"] += int(item.treatment is not None)
            counts["compound_candidates"] += int(item.compound_candidate)
    return counts


def _audit_markdown(inventory: tuple[ArtifactInventory, ...], errors: list[str]) -> str:
    """Render a complete human-auditable map without creating canonical prose."""
    counts = _summary(inventory)
    lines = [
        "# Atomic rule source audit",
        "",
        "Generated from canonical source by `tools/rule_template.py`.",
        "",
        "## Coverage",
        "",
        f"- Artifacts: {counts['artifacts']}",
        f"- Doctrine blocks: {counts['artifact:block']}",
        f"- Rules: {counts['artifact:rule']}",
        f"- Parsed items: {counts['items']}",
        f"- Candidate treatments: {counts['treatments']}",
        f"- Anti-hallucination rows: {counts['kind:anti-hallucination']}",
        f"- Compound candidates for manual review: {counts['compound_candidates']}",
        f"- Structural errors: {len(errors)}",
        "",
    ]
    if errors:
        lines.extend(["## Errors", "", *(f"- {error}" for error in errors), ""])

    lines.extend(["## Artifact map", ""])
    for artifact in inventory:
        lines.extend(
            [
                f"### `{artifact.path}`",
                "",
                "| Identifier | Kind | Lines | Treatment | Compound review |",
                "|---|---|---:|---:|---:|",
            ]
        )
        for item in artifact.items:
            lines.append(
                f"| `{item.id}` | {item.kind} | {item.line_start}-{item.line_end} | "
                f"{'yes' if item.treatment is not None else 'no'} | "
                f"{'yes' if item.compound_candidate else 'no'} |"
            )
        lines.append("")

    lines.extend(["## Exact treatments", ""])
    for artifact in inventory:
        for item in artifact.items:
            if item.treatment is None:
                continue
            lines.extend(
                [
                    f"### `{item.id}`",
                    "",
                    f"Source: `{item.path}:{item.line_start}-{item.line_end}`",
                    "",
                    "```text",
                    item.treatment,
                    "```",
                    "",
                ]
            )
    return "\n".join(lines)


def write_audit(
    inventory: tuple[ArtifactInventory, ...],
    errors: list[str],
    output_dir: Path = ARTIFACTS_DIR / "atomic-rule-template",
) -> tuple[Path, Path]:
    """Write complete JSON and Markdown audit artifacts atomically."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "inventory.json"
    markdown_path = output_dir / "audit.md"
    payload = {
        "summary": dict(_summary(inventory)),
        "errors": errors,
        "artifacts": [asdict(artifact) for artifact in inventory],
    }
    _atomic_write(json_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    _atomic_write(markdown_path, _audit_markdown(inventory, errors) + "\n")
    return json_path, markdown_path


def _atomic_write(path: Path, content: str) -> None:
    """Replace one generated artifact without exposing a partial file."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content)
    temporary.replace(path)


def _print_verbose(inventory: tuple[ArtifactInventory, ...]) -> None:
    """Print every parsed item and exact candidate treatment for manual audit."""
    for artifact in inventory:
        print(f"\n{'=' * 80}")
        print(artifact.path)
        for item in artifact.items:
            print(f"\n{item.id}")
            print(
                f"  kind={item.kind} section={item.section!r} "
                f"lines={item.line_start}-{item.line_end}"
            )
            if item.treatment is None:
                print("  treatment=(none; structural context)")
            else:
                print("  treatment:")
                for line in item.treatment.splitlines():
                    print(f"    {line}")


def main() -> None:
    """Validate the source template and optionally write a complete audit map."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="print every parsed source item")
    parser.add_argument(
        "--write-audit",
        action="store_true",
        help="write ignored JSON and Markdown audit artifacts",
    )
    args = parser.parse_args()

    inventory = load_inventory()
    errors = validate_inventory(inventory)
    counts = _summary(inventory)
    print(
        f"Atomic template: {counts['artifacts']} artifacts, {counts['items']} items, "
        f"{counts['treatments']} treatments, {len(errors)} errors"
    )
    print(
        f"  {counts['kind:anti-hallucination']} anti-hallucination rows, "
        f"{counts['compound_candidates']} compound candidates"
    )
    if args.verbose:
        _print_verbose(inventory)
    if args.write_audit:
        json_path, markdown_path = write_audit(inventory, errors)
        print(f"Wrote {json_path.relative_to(REPO)}")
        print(f"Wrote {markdown_path.relative_to(REPO)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
