"""Record the writer's test fixture in `tests/fixtures`, which needs StarCraft II and the ladder map Pylon AIE.

A bare NachOS api plays Terran against the built-in computer's very easy Zerg for 90 seconds on Pylon, sending a
worker to the enemy's start on its first turn and back home after 60 seconds, so that enemy units come into sight and
the enemy's structures leave it as copies. The game's replay is saved, then played back as each player at once while
the writer writes it, each view recording the whole conversation, so that the tests play both back with no game::

    uv run python tools/record_fixture.py

Record it again when the writer asks the game anything new: a playback answers only what was asked when it was
recorded, in the same order.
"""

import tempfile
from pathlib import Path

from sc2nachos import AbilityId, Api, Computer, Difficulty, GameTime, Race, open_replay, run_local
from sc2nachos.events import TurnEvent
from sc2nachos.run import MapFile

from sc2salsa._writer import write_from_playbacks

FIXTURES_FOLDER = Path(__file__).parents[1] / "tests" / "fixtures"
FIXTURE_NAME = "pylon-scout-90s"
_GAME_SECONDS = 90
_SCOUT_BACK_AT_SECONDS = 60


def _scout_the_enemys_main_and_come_back(api: Api) -> None:
    """Have `api` send one of its workers to the enemy's start on its first turn, and back home later."""
    scout_ids: list[int] = []

    @api.on(TurnEvent, once=True)
    def send(_: TurnEvent) -> None:
        scout = api.units.own.workers[0]
        scout_ids.append(scout.id)
        api.orders.issue(scout, AbilityId.MOVE, target=api.map.all_start_locations[1])

    @api.on(TurnEvent, at_time=GameTime(seconds=_SCOUT_BACK_AT_SECONDS))
    def come_back(_: TurnEvent) -> None:
        if (scout := api.units.own.get(scout_ids[0])) is not None:
            api.orders.issue(scout, AbilityId.MOVE, target=api.map.start_location)


def main() -> None:
    FIXTURES_FOLDER.mkdir(parents=True, exist_ok=True)
    replay = FIXTURES_FOLDER / f"{FIXTURE_NAME}.SC2Replay"
    api = Api()
    _scout_the_enemys_main_and_come_back(api)
    run_local(
        MapFile.find("PylonAIE_v4"),
        api,
        Computer(Race.ZERG, Difficulty.VERY_EASY),
        race=Race.TERRAN,
        steps_per_turn=8,
        time_limit=GameTime(seconds=_GAME_SECONDS),
        save_replay_to=replay,
    )
    with (
        open_replay(replay, player_id=1, record_to=FIXTURES_FOLDER / f"{FIXTURE_NAME}-player1.sc2rec") as first,
        open_replay(replay, player_id=2, record_to=FIXTURES_FOLDER / f"{FIXTURE_NAME}-player2.sc2rec") as second,
        tempfile.TemporaryDirectory() as scratch,
    ):
        write_from_playbacks((first, second), replay.read_bytes(), Path(scratch) / "fixture.salsa")
    for path in sorted(FIXTURES_FOLDER.glob(f"{FIXTURE_NAME}*")):
        print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
