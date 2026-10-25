# salsa

StarCraft II games as data. A `.salsa` file holds one game: every unit at every step, which units each player saw,
both players' actions and economy, the map, and the replay it came from. This repo holds the format's spec,
[`SPEC.md`](SPEC.md), and `sc2salsa`: its writer, which plays a replay back through
[NachOS](https://github.com/maxnus/NachOS), and its reader, which needs no game.

Only the spec is written yet: the plan is in [`.claude/plans/next-steps.md`](.claude/plans/next-steps.md).
