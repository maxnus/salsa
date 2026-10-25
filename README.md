# salsa

StarCraft II games as data. A `.salsa` file holds one game: every unit at every step, which units each player saw,
both players' actions and economy, the map, and the replay it came from. [NachOS](https://github.com/maxnus/NachOS)
writes the files from replays; this repo holds the format's spec and `sc2salsa`, the reader, which needs no game and
no NachOS.

Nothing is built yet: the plan is in [`.claude/plans/next-steps.md`](.claude/plans/next-steps.md), and the spec is
its first pull request.
