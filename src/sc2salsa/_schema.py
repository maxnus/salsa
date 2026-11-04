"""The tables of a `.salsa` file, version 1, as `SPEC.md` gives them: each one's columns and their types, the order
of its rows, and the members of the file."""

import pyarrow
from s2clientprotocol import score_pb2

FORMAT_VERSION = 1
"""The version of `SPEC.md` the writer writes."""

SNAPSHOT_EVERY = 28
"""The steps between snapshots of every unit, in version 1."""

# A column the format names with its own words, which a reader compares as text.
_WORDS_TYPE = pyarrow.dictionary(pyarrow.int8(), pyarrow.string())

# What a unit's row holds, after its step and unit, in both unit tables.
UNIT_ROW_FIELDS: tuple[tuple[str, pyarrow.DataType], ...] = (
    ("type", pyarrow.uint16()),
    ("owner", pyarrow.uint8()),
    ("x", pyarrow.int32()),
    ("y", pyarrow.int32()),
    ("facing", pyarrow.float32()),
    ("health", pyarrow.float32()),
    ("health_max", pyarrow.float32()),
    ("shield", pyarrow.float32()),
    ("shield_max", pyarrow.float32()),
    ("energy", pyarrow.float32()),
    ("energy_max", pyarrow.float32()),
    ("build_progress", pyarrow.float32()),
    ("flying", pyarrow.bool_()),
    ("burrowed", pyarrow.bool_()),
    ("hallucination", pyarrow.bool_()),
    ("powered", pyarrow.bool_()),
    ("active", pyarrow.bool_()),
    ("cloak", pyarrow.uint8()),
    ("attack_level", pyarrow.uint8()),
    ("armor_level", pyarrow.uint8()),
    ("shield_level", pyarrow.uint8()),
    ("minerals", pyarrow.uint16()),
    ("vespene", pyarrow.uint16()),
    ("weapon_cooldown", pyarrow.float32()),
    ("assigned_harvesters", pyarrow.uint8()),
    ("ideal_harvesters", pyarrow.uint8()),
    ("cargo_used", pyarrow.uint16()),
    ("cargo_max", pyarrow.uint16()),
    ("buff_duration_left", pyarrow.uint32()),
    ("buff_duration_max", pyarrow.uint32()),
    ("detect_range", pyarrow.float32()),
    ("radar_range", pyarrow.float32()),
    ("radius", pyarrow.float32()),
    ("add_on", pyarrow.uint32()),
    ("engaged_target", pyarrow.uint32()),
)

_STEP_AND_UNIT = (("step", pyarrow.uint32()), ("unit", pyarrow.uint32()))

ROSTER_SCHEMA = pyarrow.schema(
    [
        ("unit", pyarrow.uint32()),
        ("tag", pyarrow.uint64()),
        ("owner", pyarrow.uint8()),
        ("first_type", pyarrow.uint16()),
        ("first_step", pyarrow.uint32()),
        ("last_step", pyarrow.uint32()),
    ]
)
UNITS_SNAPSHOTS_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, *UNIT_ROW_FIELDS])
UNITS_CHANGES_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, ("listed", pyarrow.bool_()), *UNIT_ROW_FIELDS])
SIGHT_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, ("sight_1", _WORDS_TYPE), ("sight_2", _WORDS_TYPE)])
ORDERS_SCHEMA = pyarrow.schema(
    [
        *_STEP_AND_UNIT,
        ("position", pyarrow.uint8()),
        ("ability", pyarrow.uint32()),
        ("target_unit", pyarrow.uint32()),
        ("target_x", pyarrow.int32()),
        ("target_y", pyarrow.int32()),
        ("progress", pyarrow.float32()),
    ]
)
BUFFS_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, ("buff", pyarrow.uint32()), ("gained", pyarrow.bool_())])
PASSENGERS_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, ("passenger", pyarrow.uint32()), ("loaded", pyarrow.bool_())])
RALLIES_SCHEMA = pyarrow.schema(
    [
        *_STEP_AND_UNIT,
        ("position", pyarrow.uint8()),
        ("target_unit", pyarrow.uint32()),
        ("target_x", pyarrow.int32()),
        ("target_y", pyarrow.int32()),
    ]
)
EVENTS_SCHEMA = pyarrow.schema([*_STEP_AND_UNIT, ("kind", _WORDS_TYPE)])
ACTIONS_SCHEMA = pyarrow.schema(
    [
        ("step", pyarrow.uint32()),
        ("player", pyarrow.uint8()),
        ("ability", pyarrow.uint32()),
        ("units", pyarrow.list_(pyarrow.uint32())),
        ("target_unit", pyarrow.uint32()),
        ("target_x", pyarrow.int32()),
        ("target_y", pyarrow.int32()),
        ("queued", pyarrow.bool_()),
        ("autocast", pyarrow.bool_()),
    ]
)
UPGRADES_SCHEMA = pyarrow.schema(
    [("step", pyarrow.uint32()), ("player", pyarrow.uint8()), ("upgrade", pyarrow.uint32())]
)
MAP_SCHEMA = pyarrow.schema(
    [
        ("x", pyarrow.uint16()),
        ("y", pyarrow.uint16()),
        ("pathable", pyarrow.bool_()),
        ("placeable", pyarrow.bool_()),
        ("height", pyarrow.float32()),
    ]
)

# The game's player common fields the economy table holds, each a uint32, in its order.
PLAYER_COMMON_FIELDS = (
    "minerals",
    "vespene",
    "food_cap",
    "food_used",
    "food_army",
    "food_workers",
    "idle_worker_count",
    "army_count",
    "warp_gate_count",
    "larva_count",
)


def _score_detail_paths() -> tuple[tuple[str, ...], ...]:
    """The path of each value the game's score details hold, flattened in the order the protocol declares them: a
    category's, as `killed_minerals` then `army`, and a vital's, as `total_damage_dealt` then `life`."""
    paths: list[tuple[str, ...]] = []
    for field in score_pb2.ScoreDetails.DESCRIPTOR.fields:
        if field.message_type is None:
            paths.append((field.name,))
        else:
            paths.extend((field.name, part.name) for part in field.message_type.fields)
    return tuple(paths)


SCORE_DETAIL_PATHS = _score_detail_paths()
"""The fields of the game's score details, each as the path of names to it, in the economy table's order."""

ECONOMY_SCHEMA = pyarrow.schema(
    [
        ("step", pyarrow.uint32()),
        ("player", pyarrow.uint8()),
        *[(name, pyarrow.uint32()) for name in PLAYER_COMMON_FIELDS],
        ("score", pyarrow.uint32()),
        *[("_".join(path), pyarrow.float32()) for path in SCORE_DETAIL_PATHS],
    ]
)

SIGHT_WORDS = ("out", "remembered", "undetected", "seen")
"""A player's sight of a unit, in `sight.parquet`: not listed, a copy in the fog, in sight undetected, or seen."""

EVENT_KINDS = ("created", "died")
"""What `events.parquet` says of a unit: first listed, or first reported dead."""

MEMBER_NAMES = (
    "game.json",
    "replay.SC2Replay",
    "names.json",
    "map.parquet",
    "roster.parquet",
    "units_snapshots.parquet",
    "units_changes.parquet",
    "sight.parquet",
    "orders.parquet",
    "buffs.parquet",
    "passengers.parquet",
    "rallies.parquet",
    "events.parquet",
    "actions.parquet",
    "economy.parquet",
    "upgrades.parquet",
)
"""The members of a `.salsa` file, in the order the writer stores them."""
