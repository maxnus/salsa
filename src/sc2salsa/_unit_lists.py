"""`orders.parquet`, `buffs.parquet`, `passengers.parquet` and `rallies.parquet`: each unit's lists, where they
change."""

import pyarrow
from s2clientprotocol import raw_pb2

from sc2salsa._schema import BUFFS, ORDERS, PASSENGERS, RALLIES
from sc2salsa._table_builder import TableBuilder
from sc2salsa._unit_rows import UnitOf, order_list, rally_list


class UnitLists:
    """Each unit's order queue, buffs, passengers and rally targets, from its owner's view, as rows at the steps they
    change. A unit's lists are empty before its first row."""

    def __init__(self) -> None:
        self._orders = TableBuilder(ORDERS)
        self._buffs = TableBuilder(BUFFS)
        self._passengers = TableBuilder(PASSENGERS)
        self._rallies = TableBuilder(RALLIES)
        self._orders_of: dict[int, tuple[tuple[object, ...], ...]] = {}
        self._buffs_of: dict[int, frozenset[int]] = {}
        self._passengers_of: dict[int, frozenset[int]] = {}
        self._rallies_of: dict[int, tuple[tuple[object, ...], ...]] = {}

    def add(self, step: int, unit: int, entry: raw_pb2.Unit, unit_of: UnitOf) -> None:
        """The lists of `unit` at `step`, as `entry`, its owner's view's, reports them."""
        orders = order_list(entry, unit_of)
        if orders != self._orders_of.get(unit, ()):
            self._orders_of[unit] = orders
            _add_whole_list(self._orders, step, unit, orders, empty=(None, None, None, None, None))
        rallies = rally_list(entry, unit_of)
        if rallies != self._rallies_of.get(unit, ()):
            self._rallies_of[unit] = rallies
            _add_whole_list(self._rallies, step, unit, rallies, empty=(None, None, None))
        buffs = frozenset(entry.buff_ids)
        buffs_before = self._buffs_of.get(unit, frozenset())
        if buffs != buffs_before:
            self._buffs_of[unit] = buffs
            for buff in sorted(buffs - buffs_before):
                self._buffs.add((step, unit, buff, True))
            for buff in sorted(buffs_before - buffs):
                self._buffs.add((step, unit, buff, False))
        passengers = frozenset(passenger.tag for passenger in entry.passengers)
        passengers_before = self._passengers_of.get(unit, frozenset())
        if passengers != passengers_before:
            self._passengers_of[unit] = passengers
            for tag in sorted(passengers - passengers_before):
                self._passengers.add((step, unit, unit_of(tag), True))
            for tag in sorted(passengers_before - passengers):
                self._passengers.add((step, unit, unit_of(tag), False))

    def tables(self) -> dict[str, pyarrow.Table]:
        """The four tables, by member name, in the order their rows were added: by step."""
        return {
            "orders.parquet": self._orders.table(),
            "buffs.parquet": self._buffs.table(),
            "passengers.parquet": self._passengers.table(),
            "rallies.parquet": self._rallies.table(),
        }


def _add_whole_list(
    table: TableBuilder, step: int, unit: int, items: tuple[tuple[object, ...], ...], *, empty: tuple[None, ...]
) -> None:
    """Add every item of a unit's list at a step it changed, by position, or a single row with no position for an
    empty one."""
    if not items:
        table.add((step, unit, None, *empty))
    for position, item in enumerate(items):
        table.add((step, unit, position, *item))
