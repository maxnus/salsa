# Next steps for salsa

Written 2026-10-25 as a handover to the next agent, who will not have the previous agent's memory. It holds where
the work stands, what the repo owner has already decided, and the next steps in order. The working agreements are in
`.claude/CLAUDE.md`, which Claude Code loads by itself.

Keep this file current: when a step is done, say so here in the same pull request, and cut what no longer helps.

## Where things stand

- The format's spec, version 1, is `SPEC.md` (#2, and the writer's decisions in #3). No code yet.
- Two NachOS bugs that AI Arena's replays hit are fixed: `run_replay` could not play back a replay whose map is not
  where the replay names it (maxnus/NachOS#169), and `OwnUnit.engaged_target` raised for a target the game never
  listed (maxnus/NachOS#170).

## Decided, so not to be proposed again

The owner's decisions of 2026-10-25, one question at a time, so that a model or an LLM learns from a game without
playing it back. The measurements they rest on are in maxnus/NachOS#168 and #3.

- **This repo holds the format whole** (the owner, 2026-10-25, reversing the first split, in which NachOS wrote the
  files): its spec, the writer, the reader and the analysis. `sc2salsa` depends on sc2nachos, a plain dependency
  rather than an extra (over `sc2salsa[write]`), for launching the game and playing a replay back; the reader never
  imports it. Over NachOS writing the files (each change to the format a salsa PR, then a NachOS one, and pyarrow in
  NachOS), and over moving NachOS's launch and protocol layers to a package of their own, which no third user needs
  yet. PyPI takes no dependency on a git repository, so sc2salsa is published after sc2nachos.
- **The writer reads the protocol** (the owner, 2026-10-25, over NachOS's api): NachOS starts the replay on its own
  build with its map, and the writer reads each observation itself. Played as player 1 of 5030760 (30 minutes), a
  view took 4 min 39 s, against 8 min 10 s through the api, which also needs NachOS's private state for the game's
  ids, names, displays and actions.
- **Two playbacks with the fog on** (the owner, 2026-10-25, over the fog off, and over one playback as player 0): one
  as each player, every unit from its owner's view, and the map's units from a view in whose sight they are. Compared
  side by side with the fog off in all six views of three AI Arena games: own units the same at every step, every
  field equal but an order's target, which with the fog off names a copy's tag no view lists; enemies in sight, and
  undetected ones, alike; every map unit in some player's sight at some point. With the fog off, 3 to 1,290 actions a
  view named a tag no view lists; with the fog on, a copy the view lists, which matches one unit by type and spot.
  Player 0 with the fog off lists every unit with its owner's fields, but no actions, and no player's economy,
  upgrades or sight.
- **The name**: the repo `salsa`, the package `sc2salsa`, the files `.salsa` (over `sc2replaydata` and `sc2frames`).
- **A file holds every unit and each side's sight** (over the units alone, and over one player's view): every unit as
  its owner saw it, both players' actions, economy and upgrades, their units' orders, which units each player saw,
  and the map once. A player's memory of a unit is the unit at the last step it saw it, so memory needs no table of
  its own; the sight table says when the player was shown a copy, `remembered` (the owner, 2026-10-25, over three
  words).
- **Every step, exactly** (the owner's idea of checkpoints, over a sample every N steps): a snapshot of every unit
  every 28 steps, 1.25 s of game time, as a table of its own, and between, only the rows that changed. The game cannot
  resume a replay from a state, so the checkpoints are in the file. The owner chose 28 over 224, 128 and 32: denser
  snapshots cost little and make the snapshots alone a sample to read, and a power of two looked a step up no faster.
  An action comes at the step the game stamps it with, the step before the observation that reports it, in all six
  views (the owner, 2026-10-25, over the observation's); a death, with no stamp, at the observation's. The
  `.SC2Replay` is kept in the file, for anything its tables lack.
- **Every field** (over the core and the order queue): 35 a row, the owner's view's included (weapon cooldown,
  harvesters, cargo, add-on, engaged target), and tables of changes for the order queue, buffs, passengers and
  rallies. A whole row is kept where any field changed, over a column at a time, as a moving unit's x, y and facing
  change together. The eight the first spec left out (power, activity, a buff's or timed life's steps left and its
  length, detection and radar range, radius and cargo slots) made 2.8% more change rows in 5030760, nearly all from
  the steps left counting down (the owner, 2026-10-25, over leaving those out).
- **A target the file cannot name is null** (the owner, 2026-10-25, over a column of the game's tag, "I don't think
  anyone could ever do anything with the tag", and over a flag): one under a tag no view lists, as 189 probe gathers in
  5030771 and 24 in 5030760 named with the fog on.
- **Parquet with zstd** (over compressed numpy, within 10% of it in size), which pandas, polars, DuckDB and Arrow
  read.
- **One file per game** (over a folder per game, and over a table per kind across games): an uncompressed zip of its
  replay, `game.json` (map, players, races, result, build, steps, format version) and a Parquet file a table. DuckDB
  and polars do not read inside a zip, so the reader extracts one.
- **A unit is a dense index** from 0 in the order units first appear (over the game's tag), and a roster table gives
  each its tag, owner, first type and first and last steps. NachOS's ids cannot serve: they differ between the two
  players' views. A copy a player is shown in the fog is the unit of its type on its spot.
- **The unit changes are sorted by unit, then step** (the owner, 2026-10-25, over by step, then unit): 21 to 27%
  smaller at every precision. A reader loads the table once, then rebuilds a step in some 40 µs; reading one step from
  disk would need small row groups, which made the file 40 to 60% bigger and were no faster. Snapshots stay sorted by
  step (#2).
- **Lossless** (the owner, 2026-10-25, over 1/256 tile and 1/4096 turn, a quarter smaller): positions as integers of
  1/4096 tile, the grid the game reports them on; facing, which lies on no grid, as reported in float32; the rest as
  reported. Delta encoding for integer columns and byte-stream-split for float ones take a 30-minute game's units to
  some 22 MB, a third of what Parquet's default encodings make (#2).
- **The first reader** (over its tables and extracting alone): `sc2salsa.open(path)`, the facts, the replay, any table
  as a pyarrow Table, every unit `at(step)` from the nearest snapshot and the changes since, `frames(every=N)` forward
  through the game, and `extract(folder)`.

## Next

A pull request at a time, in this order (the owner, over the spec and reader first, and over the writer first):

1. In NachOS (its plan): a public way to start a replay on its own build with its map and read its observations, the
   first half of `run_replay`.
2. **The writer**, which writes a replay's file, with `pyproject.toml`, tests and CI: its tests play back
   recorded observations through NachOS's playback transport, with no game client, and read the file back with
   pyarrow against `SPEC.md`; an in-game test writes a real replay.
3. **The reader**, its fixtures written by the writer.
4. A folder of replays written across several game clients.
5. **A digest of a game for an LLM.**

Apart from these, NachOS fixes a crash its own fog-off playback has: an `OwnActionEvent` raises `UnknownTagError` for
an action on a copy that view never lists, in all six views; its target is to read as not reported (the owner,
2026-10-25, over `None`). The writer does not wait on it.

## Waiting until something needs them

- A license: the owner's call (NachOS is MIT).
- Publishing sc2salsa on PyPI: the owner's call.
