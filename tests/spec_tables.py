"""The columns `SPEC.md` gives each table, read from its Markdown, so that a test checks the writer against the spec
rather than against the writer's own schemas."""

import re
from pathlib import Path

import pyarrow

SPEC = Path(__file__).parents[1] / "SPEC.md"

_TYPES = {
    "uint8": pyarrow.uint8(),
    "uint16": pyarrow.uint16(),
    "uint32": pyarrow.uint32(),
    "uint64": pyarrow.uint64(),
    "int32": pyarrow.int32(),
    "float32": pyarrow.float32(),
    "bool": pyarrow.bool_(),
    "list<uint32>": pyarrow.list_(pyarrow.uint32()),
}
WORDS = "words"
"""The type `SPEC.md` names a `dictionary` string column: one of the format's own words."""
SCORE_DETAILS = "every field of the game's score details, flattened"
"""The row of the economy table that stands for many columns."""

_NAME = re.compile(r"`([a-z_0-9]+)`")


def _type_of(text: str) -> pyarrow.DataType | str:
    if "`dictionary` string" in text:
        return WORDS
    return _TYPES[text.strip().strip("`")]


def _sections(spec: str) -> dict[str, str]:
    """Each `##` section's text, by its heading."""
    parts = re.split(r"^## (.+)$", spec, flags=re.MULTILINE)
    return {heading.strip(): body for heading, body in zip(parts[1::2], parts[2::2], strict=True)}


def _table_rows(section: str) -> list[list[str]]:
    """The cells of each row of the first Markdown table in `section`, its header and rule left out."""
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


def _columns_of(section: str) -> list[tuple[str, pyarrow.DataType | str, str]]:
    """Each column of the section's table, with its type and what the spec says of it."""
    columns = []
    for names, type_text, *said in _table_rows(section):
        said_text = said[0] if said else ""
        found = _NAME.findall(names)
        for name in found or [names]:
            columns.append((name, _type_of(type_text), said_text))
    return columns


def spec_columns() -> dict[str, list[tuple[str, pyarrow.DataType | str]]]:
    """The columns `SPEC.md` gives each Parquet member of a file, by member name, each with its type: a pyarrow type,
    `WORDS`, or for the economy table's last row, `SCORE_DETAILS` as its name."""
    sections = _sections(SPEC.read_text(encoding="utf-8"))
    tables: dict[str, list[tuple[str, pyarrow.DataType | str]]] = {}
    for heading, body in sections.items():
        if member := re.fullmatch(r"`([a-z_]+\.parquet)`", heading):
            tables[member.group(1)] = [(name, kind) for name, kind, _ in _columns_of(body)]
    unit_columns = _columns_of(sections["The unit tables"])
    tables["units_snapshots.parquet"] = [
        (name, kind) for name, kind, said in unit_columns if "changes only" not in said
    ]
    tables["units_changes.parquet"] = [(name, kind) for name, kind, _ in unit_columns]
    tables.update(_list_tables(sections["`orders.parquet`, `buffs.parquet`, `passengers.parquet`, `rallies.parquet`"]))
    return tables


def _list_tables(section: str) -> dict[str, list[tuple[str, pyarrow.DataType | str]]]:
    """The four tables of unit lists, whose columns `SPEC.md` gives inline: a column's type follows it in parentheses,
    and the step and the unit are `uint32`, as every step and unit is."""
    tables = {}
    for table_cell, columns_cell in _table_rows(section):
        columns: list[tuple[str, pyarrow.DataType | str]] = []
        untyped: list[str] = []
        for match in re.finditer(r"`([a-z_0-9]+)`(?: \(`([a-z0-9<>]+)`[^)]*\))?", columns_cell):
            name, type_text = match.groups()
            if name in ("step", "unit"):
                columns.append((name, pyarrow.uint32()))
                continue
            untyped.append(name)
            if type_text:
                columns.extend((pending, _TYPES[type_text]) for pending in untyped)
                untyped = []
        tables[f"{table_cell.strip('`')}.parquet"] = columns
    return tables


def spec_members() -> list[str]:
    """The members of a file, in the order `SPEC.md`'s table of them gives."""
    section = _sections(SPEC.read_text(encoding="utf-8"))["The file"]
    members = []
    for row in _table_rows(section):
        member = re.search(r"`([A-Za-z_0-9.]+)`", row[0])
        assert member is not None, f"SPEC.md's table of members has a row naming none: {row}"
        members.append(member.group(1))
    return members
