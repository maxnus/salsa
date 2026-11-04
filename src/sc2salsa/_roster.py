"""Every unit of a game once, by its index in the file, and the game's tags that name it."""

from dataclasses import dataclass

import pyarrow

from sc2salsa._schema import ROSTER_SCHEMA

# Where a unit of a type stands, exactly as the game reports it: a copy in the fog replaces a unit of its type at its
# very position (in game), so this names a unit across the observation in which one replaces the other.
type Spot = tuple[int, float, float]

MAP_OWNER = 16
"""The owner the game gives the map's own units: minerals, geysers, rocks and the like."""


@dataclass(slots=True)
class RosterEntry:
    """One unit of the game: its row in `roster.parquet`."""

    tag: int | None
    owner: int
    first_type: int
    first_step: int
    last_step: int

    @property
    def is_map_unit(self) -> bool:
        """Whether the unit is the map's own, as a mineral field is."""
        return self.owner == MAP_OWNER


class Roster:
    """Every unit listed so far, in the order first listed, and what names each: the game's tags, its own and its
    copies' in either player's view, which the game gives once in a game, and a map unit's spot."""

    def __init__(self) -> None:
        self.entries: list[RosterEntry] = []
        self.unit_of_tag: dict[int, int] = {}
        self._map_unit_at_spot: dict[Spot, int] = {}
        self._spot_of_map_unit: dict[int, Spot] = {}

    def add(self, *, tag: int | None, copy_tag: int | None, owner: int, unit_type: int, step: int) -> int:
        """A new unit, first listed at `step`: under `tag`, the game's own, or only as a copy under `copy_tag`."""
        unit = len(self.entries)
        self.entries.append(RosterEntry(tag=tag, owner=owner, first_type=unit_type, first_step=step, last_step=step))
        for named_by in (tag, copy_tag):
            if named_by is not None:
                self.unit_of_tag[named_by] = unit
        return unit

    def name(self, unit: int, tag: int, *, is_copy: bool) -> None:
        """Have `tag` name `unit` too: the game's own tag for it, if not `is_copy`, or a copy's."""
        self.unit_of_tag[tag] = unit
        entry = self.entries[unit]
        if not is_copy and entry.tag is None:
            entry.tag = tag

    def map_unit_at(self, spot: Spot) -> int | None:
        """The map unit last known to stand at `spot`, if any."""
        return self._map_unit_at_spot.get(spot)

    def place_map_unit(self, unit: int, spot: Spot) -> None:
        """Know `unit`, a map unit, to stand at `spot`, as a critter moves."""
        before = self._spot_of_map_unit.get(unit)
        if before == spot:
            return
        if before is not None and self._map_unit_at_spot.get(before) == unit:
            del self._map_unit_at_spot[before]
        self._map_unit_at_spot[spot] = unit
        self._spot_of_map_unit[unit] = spot

    def forget_map_unit(self, unit: int) -> None:
        """Know `unit`, a map unit, to be dead, so that no later copy at its spot names it."""
        spot = self._spot_of_map_unit.pop(unit, None)
        if spot is not None and self._map_unit_at_spot.get(spot) == unit:
            del self._map_unit_at_spot[spot]

    def table(self) -> pyarrow.Table:
        """`roster.parquet`."""
        columns = {
            "unit": list(range(len(self.entries))),
            "tag": [entry.tag for entry in self.entries],
            "owner": [entry.owner for entry in self.entries],
            "first_type": [entry.first_type for entry in self.entries],
            "first_step": [entry.first_step for entry in self.entries],
            "last_step": [entry.last_step for entry in self.entries],
        }
        return pyarrow.Table.from_pydict(columns, schema=ROSTER_SCHEMA)
