"""A game's tables, from both players' views of its replay, step by step."""

from collections.abc import Sequence

import pyarrow
from s2clientprotocol import raw_pb2, sc2api_pb2

from sc2salsa._player_tables import PlayerTables
from sc2salsa._player_view import PlayerView, is_own_unit, spot_of
from sc2salsa._roster import MAP_OWNER, Roster
from sc2salsa._schema import EVENT_KINDS, EVENTS
from sc2salsa._sight_table import SightTable
from sc2salsa._table_builder import TableBuilder
from sc2salsa._unit_lists import UnitLists
from sc2salsa._unit_rows import unit_row
from sc2salsa._unit_tables import UnitTables

_VISIBLE = raw_pb2.DisplayType.Visible
_COPY = raw_pb2.DisplayType.Snapshot
_CREATED, _DIED = range(len(EVENT_KINDS))


class GameRecorder:
    """Every table of a game's file but the map's, from the observations of both players' views, one step at a
    time: each player's units as its own view reports them, and the map's as a view in whose sight they are does,
    as last seen while in neither's, or as their copies before either player sees them."""

    def __init__(self) -> None:
        self.roster = Roster()
        self.views = (PlayerView(1, self.roster), PlayerView(2, self.roster))
        self._units = UnitTables()
        self._lists = UnitLists()
        self._sight = SightTable()
        self._players = PlayerTables()
        self._events = TableBuilder(EVENTS, words={"kind": EVENT_KINDS})
        self._dead: set[int] = set()
        self._map_units_alive: set[int] = set()
        self._map_unit_rows: dict[int, tuple[object, ...]] = {}

    def add_step(self, step: int, observations: Sequence[sc2api_pb2.ResponseObservation]) -> None:
        """Both views' observations at `step`, player 1's first."""
        for view, observation in zip(self.views, observations, strict=True):
            view.read(observation)
        units_before = len(self.roster.entries)
        # A unit is named first by its owner's view, which reports its owner and its type.
        for view in self.views:
            view.name_own_units(step)
        for view in self.views:
            view.name_other_units(step)
        for unit in range(units_before, len(self.roster.entries)):
            self._events.add((step, unit, _CREATED))
            if self.roster.entries[unit].is_map_unit:
                self._map_units_alive.add(unit)
        self._record_deaths(step)
        rows = self._own_unit_rows(step)
        rows.update(self._map_unit_rows_at(step))
        self._units.add_step(step, rows)
        self._sight.add_step(step, self.views[0].sight(), self.views[1].sight())
        for view in self.views:
            self._players.add_step(step, view)

    def tables(self) -> dict[str, pyarrow.Table]:
        """Every table but the map's, by member name, each in the order its rows were added."""
        return {
            "roster.parquet": self.roster.table(),
            "units_snapshots.parquet": self._units.snapshots(),
            "units_changes.parquet": self._units.changes(),
            "sight.parquet": self._sight.table(),
            **self._lists.tables(),
            "events.parquet": self._events.table(),
            **self._players.tables(),
        }

    def _record_deaths(self, step: int) -> None:
        """Note each unit first reported dead at `step`, in either view: the game reports a death to both players at
        the same step, those out of their sight too (in game)."""
        unit_of_tag = self.roster.unit_of_tag
        for view in self.views:
            for tag in view.observation.observation.raw_data.event.dead_units:
                unit = unit_of_tag.get(tag)
                if unit is None or unit in self._dead:
                    continue
                self._dead.add(unit)
                self._events.add((step, unit, _DIED))
                if unit in self._map_units_alive:
                    self._map_units_alive.discard(unit)
                    self.roster.forget_map_unit(unit)

    def _own_unit_rows(self, step: int) -> dict[int, tuple[object, ...]]:
        """The row of each player's unit its own view lists at `step`, with its lists recorded."""
        rows: dict[int, tuple[object, ...]] = {}
        unit_of_tag = self.roster.unit_of_tag
        entries = self.roster.entries
        for view in self.views:
            unit_of = view.unit_of
            for tag, entry in view.entries.items():
                if is_own_unit(entry):
                    unit = unit_of_tag[tag]
                    rows[unit] = unit_row(entry, unit_of)
                    entries[unit].last_step = step
                    self._lists.add(step, unit, entry, unit_of)
        return rows

    def _map_unit_rows_at(self, step: int) -> dict[int, tuple[object, ...]]:
        """The row of each map unit alive at `step`: as a view in whose sight it is reports it, player 1's first, as
        last seen while in neither's, or, before either player sees it, as its copy."""
        alive = self._map_units_alive
        unit_of_tag = self.roster.unit_of_tag
        rows: dict[int, tuple[object, ...]] = {}
        for view in self.views:
            for tag, entry in view.entries.items():
                if entry.owner != MAP_OWNER:
                    continue
                unit = unit_of_tag.get(tag)
                if unit not in alive or unit in rows:
                    continue
                if entry.display_type == _VISIBLE:
                    rows[unit] = self._map_unit_rows[unit] = unit_row(entry, view.unit_of)
                    self.roster.place_map_unit(unit, spot_of(entry))
                elif entry.display_type == _COPY and unit not in self._map_unit_rows:
                    self._map_unit_rows[unit] = unit_row(entry, view.unit_of)
        entries = self.roster.entries
        for unit in alive:
            if unit not in rows:
                rows[unit] = self._map_unit_rows[unit]
            entries[unit].last_step = step
        return rows
