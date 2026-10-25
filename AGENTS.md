# AGENTS.md

## Project overview

**salsa** (package `sc2salsa`) is the `.salsa` file format for StarCraft II games: its spec, the writer, the reader,
and later a digest of a game for an LLM. A file holds one game: every unit at every step, which units each player
saw, both players' actions and economy, the map, and the replay it came from. The writer plays a replay back through
[NachOS](https://github.com/maxnus/NachOS), once as each player. The plan is in `.claude/plans/next-steps.md`.

## Keep this file small

Every agent reads all of it before every task. It takes rules for writing code and docs here, a line or two each. A
line belongs here only if you can name the task whose outcome it changes. Delete a line the code has overtaken.

## Core rules

- **The reader needs pyarrow and the file alone.** The package depends on NachOS for the writer, which launches the
  game through it; the reader never imports NachOS nor needs a game client.
- **The spec is the contract.** Every file says the format version it was written in; the writer writes the newest,
  and the reader reads every version the spec has had. A change to the format is a new version, never an edit to an
  old one, and changes the spec, the writer and the reader in one pull request.
- **Store the game's own values, never NachOS's names.** Unit types, abilities, buffs and upgrades are the game's
  integer ids, with a table of names beside them where it helps; a unit is the file's dense index, with its tag in the
  roster.
- **Measure before deciding the format.** A choice of encoding, order or precision rests on sizes and read times
  measured on real 30-minute games, stated in the commit message and the PR.

## Python

Use this repository's own environment, `.venv`, and run every tool through `uv run`. Pass `encoding="utf-8"` to
`Path.read_text` and `Path.write_text`, which otherwise take the locale's encoding.

## Code style

NachOS's [`docs/maintaining/code-style.md`](https://github.com/maxnus/NachOS/blob/main/docs/maintaining/code-style.md)
says how code and docstrings are named and written, here too. Never a one-word name for a constant or a helper.

## Testing

`pytest`, with no game client: the writer's tests play back recorded observations, and the reader's read small
`.salsa` files the writer wrote, in `tests/fixtures/`, each with a line saying how it was made. The commands come with
the writer's pull request.
