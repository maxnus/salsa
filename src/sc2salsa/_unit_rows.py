"""A unit's row and its lists, as one view's entry for it reports them, in the order `SPEC.md` gives their columns."""

from collections.abc import Callable

from s2clientprotocol import common_pb2, raw_pb2

# A position is an integer of 1/4096 tile, the grid the game reports positions on.
_POSITION_SCALE = 4096

_UNIT_FIELDS = raw_pb2.Unit.DESCRIPTOR.fields_by_name
# The entry's field each column after the position reads, in the columns' order: `None` where a field is unset.
_FACING_TO_SHIELD_LEVEL = tuple(
    _UNIT_FIELDS[name]
    for name in (
        "facing",
        "health",
        "health_max",
        "shield",
        "shield_max",
        "energy",
        "energy_max",
        "build_progress",
        "is_flying",
        "is_burrowed",
        "is_hallucination",
        "is_powered",
        "is_active",
        "cloak",
        "attack_upgrade_level",
        "armor_upgrade_level",
        "shield_upgrade_level",
        "mineral_contents",
        "vespene_contents",
        "weapon_cooldown",
        "assigned_harvesters",
        "ideal_harvesters",
        "cargo_space_taken",
        "cargo_space_max",
    )
)
_RANGES_AND_RADIUS = tuple(_UNIT_FIELDS[name] for name in ("detect_range", "radar_range", "radius"))
_OWNER_FIELD = _UNIT_FIELDS["owner"]
_BUFF_DURATION_REMAIN = _UNIT_FIELDS["buff_duration_remain"]
_BUFF_DURATION_MAX = _UNIT_FIELDS["buff_duration_max"]
_ADD_ON_TAG = _UNIT_FIELDS["add_on_tag"]
_ENGAGED_TARGET_TAG = _UNIT_FIELDS["engaged_target_tag"]

# A target that names no point.
_NO_POINT = (None, None)

type UnitOf = Callable[[int], int | None]
"""The unit a tag names, `None` for one no view listed."""


def position_of(x: float) -> int:
    """`x`, a coordinate in tiles, in 1/4096 tile."""
    return round(x * _POSITION_SCALE)


def unit_row(entry: raw_pb2.Unit, unit_of: UnitOf) -> tuple[object, ...]:
    """`entry`'s row in the unit tables, after its step and unit: `None` for a field the game left unset, and for the
    steps left of a timed life or buff where it has neither, which the game reports as a maximum of 0."""
    fields = dict(entry.ListFields())
    buff_duration_max = fields.get(_BUFF_DURATION_MAX)
    has_buff_duration = bool(buff_duration_max)
    add_on_tag = fields.get(_ADD_ON_TAG)
    engaged_target_tag = fields.get(_ENGAGED_TARGET_TAG)
    return (
        entry.unit_type,
        fields.get(_OWNER_FIELD),
        position_of(entry.pos.x),
        position_of(entry.pos.y),
        *[fields.get(field) for field in _FACING_TO_SHIELD_LEVEL],
        fields.get(_BUFF_DURATION_REMAIN) if has_buff_duration else None,
        buff_duration_max if has_buff_duration else None,
        *[fields.get(field) for field in _RANGES_AND_RADIUS],
        unit_of(add_on_tag) if add_on_tag else None,
        unit_of(engaged_target_tag) if engaged_target_tag else None,
    )


def order_list(entry: raw_pb2.Unit, unit_of: UnitOf) -> tuple[tuple[object, ...], ...]:
    """`entry`'s order queue, each order its `ability`, `target_unit`, `target_x`, `target_y` and `progress`."""
    return tuple(
        (
            order.ability_id,
            unit_of(order.target_unit_tag) if order.HasField("target_unit_tag") else None,
            *(_position_pair(order.target_world_space_pos) if order.HasField("target_world_space_pos") else _NO_POINT),
            order.progress if order.HasField("progress") else None,
        )
        for order in entry.orders
    )


def rally_list(entry: raw_pb2.Unit, unit_of: UnitOf) -> tuple[tuple[object, ...], ...]:
    """`entry`'s rally targets, each its `target_unit`, `target_x` and `target_y`."""
    return tuple(
        (
            unit_of(rally.tag) if rally.HasField("tag") else None,
            *(_position_pair(rally.point) if rally.HasField("point") else _NO_POINT),
        )
        for rally in entry.rally_targets
    )


def _position_pair(point: common_pb2.Point2D | common_pb2.Point) -> tuple[int, int]:
    return (position_of(point.x), position_of(point.y))
