# Next steps for salsa

Written 2026-10-25 as a handover to the next agent, who will not have the previous agent's memory. It holds where
the work stands, what the repo owner has already decided, and the next steps in order. The working agreements are in
`.claude/CLAUDE.md`, which Claude Code loads by itself.

Keep this file current: when a step is done, say so here in the same pull request, and cut what no longer helps.

## Where things stand

- The repo holds its plan, and no code yet. NachOS writes the files; its own plan, NachOS's
  `.claude/plans/next-steps.md` under "Writing a replay's whole game for salsa", holds the writer's part
  (maxnus/NachOS#168).
- Two NachOS bugs that AI Arena's replays hit come first: `run_replay` could not play back a replay whose map is not
  where the replay names it (maxnus/NachOS#169, merged), and `OwnUnit.engaged_target` raised for a target the game
  never listed (maxnus/NachOS#170).

## Decided, so not to be proposed again

The owner's decisions of 2026-10-25, one question at a time, so that a model or an LLM learns from a game without
playing it back. The measurements they rest on are in maxnus/NachOS#168.

- **The split** (the owner): NachOS writes the files; the format's spec, the reader and the analysis are this repo,
  which needs pyarrow and never NachOS. The spec lives here, with a version in every file: NachOS's writer writes one
  version, and the reader reads every version it knows.
- **The name**: the repo `salsa`, the package `sc2salsa`, the files `.salsa` (over `sc2replaydata` and `sc2frames`).
- **A file holds the truth and each side's sight** (over the truth alone, and over one player's view): every unit as
  it is, both players' actions, economy and upgrades, their own units' orders, which units each player saw, and the
  map once. NachOS plays the replay as each player with the fog off and merges the two views by the game's tag. A
  player's memory of a unit is the truth at the last step it saw it, so memory needs no table of its own.
- **Every step, exactly** (the owner's idea of checkpoints, over a sample every N steps): a snapshot of every unit
  every 28 steps, 1.25 s of game time, as a table of its own, and between, only the rows that changed. The game cannot
  resume a replay from a state, so the checkpoints are in the file. The owner chose 28 over 224, 128 and 32: denser
  snapshots cost little and make the snapshots alone a sample to read, and a power of two looked a step up no faster.
  Events and actions come at the step the game reports them, in the observation after. The `.SC2Replay` is kept in
  the file, for anything its tables lack.
- **Every field** (over the core and the order queue): 27 a row, each owner's view's included (weapon cooldown,
  harvesters, cargo, add-on, engaged target), and tables of changes for the order queue, buffs, passengers and
  rallies. A whole row is kept where any field changed, over a column at a time, as a moving unit's x, y and facing
  change together.
- **Parquet with zstd** (over compressed numpy, within 10% of it in size), which pandas, polars, DuckDB and Arrow
  read. NachOS's writer gets its pyarrow from an optional extra, `sc2nachos[dataset]`.
- **One file per game** (over a folder per game, and over a table per kind across games): an uncompressed zip of its
  replay, `game.json` (map, players, races, result, build, steps, format version) and a Parquet file a table. DuckDB
  and polars do not read inside a zip, so the reader extracts one.
- **A unit is a dense index** from 0 in the order units first appear (over the game's tag), and a roster table gives
  each its tag, owner, first type and first and last steps. NachOS's ids cannot serve: they differ between the two
  players' views.
- **The first reader** (over its tables and extracting alone): `sc2salsa.open(path)`, the facts, the replay, any table
  as a pyarrow Table, every unit `at(step)` from the nearest snapshot and the changes since, `frames(every=N)` forward
  through the game, and `extract(folder)`.

## Next

A pull request at a time, in this order (the owner, over the spec and reader first, and over the writer first):

1. **The format's spec**, version 1: every table, column, type and encoding, measuring what makes a file smaller
   first. A 30-minute AI Arena game came to 77 to 97 MB with every field at every step; the changes sorted by unit
   rather than by step, and positions and facing stored coarser, may shrink it. The measurements may use NachOS and a
   game; the spec must not need them.
2. NachOS writes the files (NachOS's plan), tested there against the spec with pyarrow alone.
3. **The reader**, with `pyproject.toml`, tests and CI, its fixtures written by NachOS's writer. NachOS's `dev` extra
   then installs sc2salsa from this repo, until the owner publishes it, for a round trip.
4. NachOS writes a folder of replays across several game clients (NachOS's plan).
5. **A digest of a game for an LLM.**

## Waiting until something needs them

- A license: the owner's call (NachOS is MIT).
- Publishing sc2salsa on PyPI: the owner's call.
