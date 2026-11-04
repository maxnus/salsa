"""`sight.parquet`: which units each player saw, at the steps that changes."""

import pyarrow

from sc2salsa._player_view import SIGHT_OUT
from sc2salsa._schema import SIGHT_SCHEMA, SIGHT_WORDS
from sc2salsa._table_builder import TableBuilder

_BOTH_OUT = (SIGHT_OUT, SIGHT_OUT)


class SightTable:
    """Each player's sight of each unit: a row at a unit's first step, and at each step either player's sight of it
    changes, a unit out of both players' lists reading `out` for both."""

    def __init__(self) -> None:
        self._rows = TableBuilder(SIGHT_SCHEMA, words={"sight_1": SIGHT_WORDS, "sight_2": SIGHT_WORDS})
        self._sight_before: dict[int, tuple[int, int]] = {}

    def add_step(self, step: int, first: dict[int, int], second: dict[int, int]) -> None:
        """Each player's sight at `step` of the units its view lists, by unit."""
        sight = {
            unit: (first.get(unit, SIGHT_OUT), second.get(unit, SIGHT_OUT)) for unit in first.keys() | second.keys()
        }
        sight_before = self._sight_before
        for unit, both in sight.items():
            if sight_before.get(unit) != both:
                self._rows.add((step, unit, *both))
        for unit in sight_before.keys() - sight.keys():
            self._rows.add((step, unit, *_BOTH_OUT))
        self._sight_before = sight

    def table(self) -> pyarrow.Table:
        """`sight.parquet`, in the order the rows were added: by step. `SPEC.md` sorts it by unit, then step."""
        return self._rows.table()
