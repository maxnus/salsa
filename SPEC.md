# The `.salsa` format, version 1

A `.salsa` file holds one StarCraft II game: every unit at every step, which units each player saw, both players'
actions and economy, the map, and the replay the file was written from. This is its spec. NachOS's writer writes
version 1; a reader reads every version this spec has had. Version 1 may still change until the writer first writes
it; after that, a change is a new version.

## The file

An uncompressed zip, its members stored rather than deflated, since the tables are compressed already:

| Member | Holds |
|---|---|
| `game.json` | the game's facts, and the format version |
| `replay.SC2Replay` | the replay the file was written from, byte for byte |
| `names.json` | the game's own names for the ids the tables hold |
| `map.parquet` | the map's tiles |
| `roster.parquet` | each unit once |
| `units_snapshots.parquet` | every unit listed, every 28 steps |
| `units_changes.parquet` | a unit's row at each step it changed between snapshots |
| `sight.parquet` | which units each player saw |
| `orders.parquet` | each unit's order queue |
| `buffs.parquet` | the buffs each unit gained and lost |
| `passengers.parquet` | the units each unit held |
| `rallies.parquet` | each structure's rally targets |
| `events.parquet` | units created and dead |
| `actions.parquet` | each player's actions |
| `economy.parquet` | each player's resources, supply and score |
| `upgrades.parquet` | each player's upgrades |

A reader ignores a member it does not know, so a later version can add one.

## Conventions

- **Steps.** A step is the game's loop, from 0, 22.4 a second at the ladder's speed. Every table's `step` is a
  `uint32`.
- **What the game reports.** Values are the game's own: unit types, abilities, buffs and upgrades are its integer ids,
  and `names.json` gives its names for them. Nothing in a file comes from NachOS's names.
- **The truth.** The writer plays the replay back once as each player with the fog off. Every unit is as it was, and
  a value only its owner's view reports, such as orders or a weapon's cooldown, is from that view.
- **Events at the step reported.** The game reports a death or an action in the observation after it, so its `step` is
  that observation's.
- **A unit** is its index in the roster: 0, 1, 2 in the order units are first listed. A column naming a unit is a
  `uint32`, null where it names none.
- **Positions** are integers of 1/4096 tile, the grid the game reports them on: `x` 524288 is 128.0 tiles. A position
  column is an `int32`.
- **Not reported** is null, never 0: a field the game did not report for a unit at a step, such as the health of a
  unit no view saw in full.
- **Owners** are the game's: 1 and 2 for the players, 16 for the map's units.
- **Encoding.** Parquet, zstd. The writer uses delta encoding for integer columns and byte-stream-split for float
  columns, where they shrink a table; a reader needs neither to read it.

## `game.json`

The game's facts, in this shape (the values are an example):

```json
{
  "format_version": 1,
  "written_by": "sc2nachos 0.0.1",
  "map_name": "Pylon AIE",
  "map_file": "PylonAIE_v4.SC2Map",
  "base_build": 75689,
  "data_version": "B89B5D6FA7CBF6452E721311BFBC6CB2",
  "steps": 43936,
  "players": [
    {"player_id": 1, "race_requested": "zerg", "race_actual": "zerg", "result": "victory", "apm": 17297},
    {"player_id": 2, "race_requested": "protoss", "race_actual": "protoss", "result": "defeat", "apm": 14298}
  ],
  "map": {"width": 184, "height": 184, "playable": [24, 18, 160, 166], "start_locations": [[134.5, 140.5], [49.5, 43.5]]},
  "snapshot_every": 28
}
```

`steps` is the replay's length. Races are `terran`, `zerg`, `protoss` or `random`; results are `victory`, `defeat`,
`tie` or `undecided`. `map` is the map's size, its playable area and its start locations, in tiles, as the game's info
gives them. `snapshot_every` is 28 in version 1.

## `names.json`

```json
{"unit_types": {"48": "Marine"}, "abilities": {"3674": "Attack"}, "buffs": {"27": "Stimpack"}, "upgrades": {"15": "Stimpack"}}
```

The names the game's data gives each id the file holds, as the game's tables at the game's start name them.

## `map.parquet`

A row per tile of the map, by `x`, then `y`.

| Column | Type | |
|---|---|---|
| `x`, `y` | `uint16` | the tile |
| `pathable` | `bool` | as the game's pathing grid gives it at the start |
| `placeable` | `bool` | as the game's placement grid gives it |
| `height` | `float32` | the terrain's height |

## `roster.parquet`

A row per unit, by `unit`.

| Column | Type | |
|---|---|---|
| `unit` | `uint32` | its index |
| `tag` | `uint64` | the game's tag for it, as both views list it with the fog off |
| `owner` | `uint8` | its owner when first listed |
| `first_type` | `uint16` | its type when first listed |
| `first_step`, `last_step` | `uint32` | the first and the last step it was listed at |

## The unit tables

`units_snapshots.parquet` holds a row for every unit listed at each step divisible by `snapshot_every`, step 0
included, by `step`, then `unit`. `units_changes.parquet` holds a row for a unit at each other step at which it is
listed and was not at the step before, any column differs from the step before, or it is no longer listed. It is
sorted by `unit`, then `step`.

Every unit at a step is the snapshot at or before it, each unit then taking its last change after the snapshot and up
to the step; a unit whose last change reads `listed` false is not listed then.

| Column | Type | |
|---|---|---|
| `step` | `uint32` | |
| `unit` | `uint32` | |
| `listed` | `bool` | changes only: false where the unit is no longer listed, dead or inside another unit, with its last values |
| `type` | `uint16` | |
| `owner` | `uint8` | |
| `x`, `y` | `int32` | in 1/4096 tile |
| `facing` | `float32` | radians, as reported |
| `health`, `health_max`, `shield`, `shield_max`, `energy`, `energy_max` | `float32` | |
| `build_progress` | `float32` | 0 to 1 |
| `flying`, `burrowed`, `hallucination` | `bool` | |
| `cloak` | `uint8` | the game's cloak state, from its owner's view: whether it is cloaked |
| `attack_level`, `armor_level`, `shield_level` | `uint8` | |
| `minerals`, `vespene` | `uint16` | what a resource holds |
| `weapon_cooldown` | `float32` | steps, from its owner's view |
| `assigned_harvesters`, `ideal_harvesters`, `cargo_used` | `uint8` | from its owner's view |
| `add_on`, `engaged_target` | `uint32` | units, from its owner's view |

## `sight.parquet`

By `unit`, then `step`: a row at a unit's first step, and at each step either player's sight of it changes.

| Column | Type | |
|---|---|---|
| `step`, `unit` | `uint32` | |
| `sight_1`, `sight_2` | `uint8` | as that player's view lists the unit: 0 out of its sight, 1 in its sight but cloaked or burrowed and undetected, 2 in its sight and seen |

What a player remembered of a unit is the unit as it was at the last step that player saw it.

## `orders.parquet`, `buffs.parquet`, `passengers.parquet`, `rallies.parquet`

Each by `unit`, then `step`, with rows only where the unit's list changes. Orders, passengers and rallies are their
owner's view; buffs are every unit's.

| Table | Columns |
|---|---|
| `orders` | `step`, `unit`, `position` (`uint8`, 0 the current order), `ability` (`uint32`), `target_unit` (`uint32`), `target_x`, `target_y` (`int32`), `progress` (`float32`) |
| `buffs` | `step`, `unit`, `buff` (`uint32`), `gained` (`bool`) |
| `passengers` | `step`, `unit`, `passenger` (`uint32`), `loaded` (`bool`) |
| `rallies` | `step`, `unit`, `position` (`uint8`), `target_unit` (`uint32`), `target_x`, `target_y` (`int32`) |

At a step where a unit's orders or rallies change, the table holds its whole list then: every position, or a single
row with `position` null for an empty one.

## `events.parquet`

By `step`, then `unit`.

| Column | Type | |
|---|---|---|
| `step`, `unit` | `uint32` | |
| `kind` | `string` | `created`, first listed; `died`, reported dead in either view |

## `actions.parquet`

By `step`, then `player`: what each player's view reports it did.

| Column | Type | |
|---|---|---|
| `step` | `uint32` | |
| `player` | `uint8` | |
| `ability` | `uint32` | |
| `units` | `list<uint32>` | the units it was given to |
| `target_unit` | `uint32` | |
| `target_x`, `target_y` | `int32` | in 1/4096 tile |
| `queued` | `bool` | |
| `autocast` | `bool` | true for an autocast switched, which names no target |

## `economy.parquet`

By `player`, then `step`: a row at step 0 and at each step any column changes.

| Column | Type | |
|---|---|---|
| `step` | `uint32` | |
| `player` | `uint8` | |
| `minerals`, `vespene`, `food_cap`, `food_used`, `food_army`, `food_workers`, `idle_worker_count`, `army_count`, `warp_gate_count`, `larva_count` | `uint32` | the game's player common fields |
| `score` | `uint32` | |
| every field of the game's score details, flattened | `float32` | a category's as `killed_minerals_army` and the like, a vital's as `total_damage_dealt_life` |

## `upgrades.parquet`

By `player`, then `step`: a row at the step each upgrade is first reported.

| Column | Type | |
|---|---|---|
| `step` | `uint32` | |
| `player` | `uint8` | |
| `upgrade` | `uint32` | |
