"""`units_snapshots.parquet` and `units_changes.parquet`: every unit listed at each step, as rows."""

import pyarrow

from sc2salsa._schema import SNAPSHOT_EVERY, UNITS_CHANGES, UNITS_SNAPSHOTS
from sc2salsa._table_builder import TableBuilder


class UnitTables:
    """Every unit listed, at each step it is: whole at each step divisible by `SNAPSHOT_EVERY`, and at each other step
    the rows of units first listed, changed in any column, or no longer listed since the step before."""

    def __init__(self) -> None:
        self._snapshots = TableBuilder(UNITS_SNAPSHOTS)
        self._changes = TableBuilder(UNITS_CHANGES)
        self._rows_before: dict[int, tuple[object, ...]] = {}

    def add_step(self, step: int, rows: dict[int, tuple[object, ...]]) -> None:
        """The units listed at `step`, each unit's row by unit."""
        if step % SNAPSHOT_EVERY == 0:
            for unit in sorted(rows):
                self._snapshots.add((step, unit, *rows[unit]))
        else:
            rows_before = self._rows_before
            for unit, row in rows.items():
                if rows_before.get(unit) != row:
                    self._changes.add((step, unit, True, *row))
            for unit, row in rows_before.items():
                if unit not in rows:
                    # No longer listed, with its last values.
                    self._changes.add((step, unit, False, *row))
        self._rows_before = rows

    def snapshots(self) -> pyarrow.Table:
        """`units_snapshots.parquet`, by step, then unit."""
        return self._snapshots.table()

    def changes(self) -> pyarrow.Table:
        """`units_changes.parquet`, in the order the rows were added: by step. `SPEC.md` sorts it by unit, then step."""
        return self._changes.table()
