# salsa

StarCraft II games as data. A `.salsa` file holds one game: every unit at every step, which units each player saw,
both players' actions and economy, the map, and the replay it came from. This repo holds the format's spec,
[`SPEC.md`](SPEC.md), and `sc2salsa`: its writer, which plays a replay back through
[NachOS](https://github.com/maxnus/NachOS), and its reader, which needs no game.

The writer plays a replay back as each of its two players at once, fog on, on two StarCraft II clients that NachOS
starts on the replay's own build:

```python
import sc2salsa

sc2salsa.write_salsa_file("games/4933221.SC2Replay", "games/4933221.salsa")
```

The reader comes next: the plan is in [`.claude/plans/next-steps.md`](.claude/plans/next-steps.md).
