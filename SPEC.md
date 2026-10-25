# The `.salsa` format, version 1

A `.salsa` file holds one StarCraft II game: every unit at every step, which units each player saw, both players'
actions and economy, the map, and the replay the file was written from. This is its spec. sc2salsa's writer writes
version 1; its reader reads every version this spec has had. Version 1 may still change until the writer first
writes it; after that, a change is a new version.

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
- **The format's own words.** A value the game has no number for, such as an event's kind or a player's sight of a
  unit, is a `dictionary` string column: one of the words this spec lists, stored as a small index into the column's
  words, which a reader can compare as text.
- **Two views.** The writer plays the replay back twice, at every step, once as each player, with the fog on, as the
  game was played. A player's unit is as its owner's view reports it, every field in full. A map unit is as a view in
  whose sight it is reports it, and as last seen while in neither's; before either player sees it, as the copy each
  view lists from the start reports it, its type and its spot.
- **Steps of events.** An action carries the step the game ran it on, as the game stamps it, which is the step before
  the observation that reports it (in game). The game stamps a death with no step: a death carries the step of the
  first observation that reports it.
- **A unit** is its index in the roster: 0, 1, 2 in the order units are first listed. A column naming a unit is a
  `uint32`, null where it names none. The game names a unit a player remembers in the fog by the tag of the copy it
  shows the player: such a column names the unit the copy is of, the one of its type on its spot, and is null where
  none is, or where the tag is one no view lists.
- **Positions** are integers of 1/4096 tile, the grid the game reports them on: `x` 524288 is 128.0 tiles. A position
  column is an `int32`.
- **Not reported** is null, never 0: a field the game left unset for a unit at a step, such as a mineral field's
  contents before either player sees it.
- **Owners** are the game's: 1 and 2 for the players, 16 for the map's units.
- **Encoding.** Parquet, zstd. The writer uses delta encoding for integer columns and byte-stream-split for float
  columns, where they shrink a table; a reader needs neither to read it.

## `game.json`

The game's facts, in this shape (the values are an example):

```json
{
  "format_version": 1,
  "written_by": "sc2salsa 0.0.1",
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
| `tag` | `uint64` | the game's tag for it, never a copy's: null for a map unit no player ever sees |
| `owner` | `uint8` | its owner when first listed |
| `first_type` | `uint16` | its type when first listed |
| `first_step`, `last_step` | `uint32` | the first and the last step it was listed at: by its owner's view, or for a map unit, by either view, its copy included |

## The unit tables

`units_snapshots.parquet` holds a row for every unit listed at each step divisible by `snapshot_every`, step 0
included, by `step`, then `unit`. `units_changes.parquet` holds a row for a unit at each other step at which it is
listed and was not at the step before, any column differs from the step before, or it is no longer listed. It is
sorted by `unit`, then `step`.

Every unit at a step is read from the snapshot at or before it and the changes after the snapshot, up to the step:
each unit takes its last change there if it has one, a unit first listed after the snapshot comes from its changes,
and a unit whose last change reads `listed` false is not listed then.

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
| `powered` | `bool` | a Protoss structure in a pylon's power field |
| `active` | `bool` | busy: moving, attacking, gathering, training or researching |
| `cloak` | `uint8` | the game's cloak state |
| `attack_level`, `armor_level`, `shield_level` | `uint8` | |
| `minerals`, `vespene` | `uint16` | what a resource holds |
| `weapon_cooldown` | `float32` | steps |
| `assigned_harvesters`, `ideal_harvesters`, `cargo_used`, `cargo_max` | `uint8` | |
| `buff_duration_left`, `buff_duration_max` | `uint32` | steps, of the unit's timed life, as a MULE's, or of a timed buff on it, as an inject's; null where it has neither, which the game reports as a maximum of 0 |
| `detect_range`, `radar_range`, `radius` | `float32` | tiles |
| `add_on`, `engaged_target` | `uint32` | units |

## `sight.parquet`

By `unit`, then `step`: a row at a unit's first step, and at each step either player's sight of it changes.

| Column | Type | |
|---|---|---|
| `step`, `unit` | `uint32` | |
| `sight_1`, `sight_2` | `dictionary` string | as that player's view lists the unit: `out`, not listed; `remembered`, out of its sight, shown as a copy in the fog; `undetected`, in its sight, cloaked or burrowed; or `seen` |

A unit a player remembers is as that player last saw it: its row at the last step it read `seen`, or for a map unit
not yet seen, its type and its spot.

## `orders.parquet`, `buffs.parquet`, `passengers.parquet`, `rallies.parquet`

Each by `unit`, then `step`, with rows only where the unit's list changes, in any column: an order's `progress` alone
changing is a change. Each is as the unit's row is, from its owner's view.

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
| `kind` | `dictionary` string | `created`, first listed; `died`, first reported dead |

## `actions.parquet`

By `step`, then `player`: what each player's view reports it did.

| Column | Type | |
|---|---|---|
| `step` | `uint32` | the step the game ran it on |
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
