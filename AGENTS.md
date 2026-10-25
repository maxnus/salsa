# AGENTS.md

## Project overview

**salsa** (package `sc2salsa`) is the `.salsa` file format for StarCraft II games and its reader. A file holds one
game: every unit at every step, which units each player saw, both players' actions and economy, the map, and the
replay it came from. [NachOS](https://github.com/maxnus/NachOS) writes the files from replays
(`sc2nachos.dataset.write_salsa`); this repo holds the format's spec and the reader, and later a digest of a game for
an LLM. The plan is in `.claude/plans/next-steps.md`.

## Keep this file small

Every agent reads all of it before every task. It takes rules for writing code and docs here, a line or two each. A
line belongs here only if you can name the task whose outcome it changes. Delete a line the code has overtaken.

## Core rules

- **Never depend on NachOS, nor on a game client.** The reader needs pyarrow and the file alone. A file NachOS wrote
  is a test fixture, never an import.
- **The spec is the contract between two repos.** It lives here. Every file says the format version it was written
  in; NachOS writes one version, and the reader reads every version the spec has had. A change to the format is a new
  version, never an edit to an old one.
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

`pytest`, with no game client: the fixtures are small `.salsa` files written by NachOS, in `tests/fixtures/`, each
with a line saying how it was written. The commands come with the reader's pull request.
