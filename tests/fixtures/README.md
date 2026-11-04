# Test fixtures

- `pylon-scout-90s.SC2Replay`, `pylon-scout-90s-player1.sc2rec`, `pylon-scout-90s-player2.sc2rec`: a 90-second game on
  Pylon AIE, build 75689, of a bare NachOS api playing Terran against the built-in computer's very easy Zerg, sending a
  worker to the enemy's start and back after 60 seconds; its replay, and both players' views of it recorded while the
  writer wrote it. Made by `uv run python tools/record_fixture.py`, which says when to make them again.
