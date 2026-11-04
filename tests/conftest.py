"""The writer's fixture, written once for every test: the file the writer writes from both recorded views of a
90-second game on Pylon (`tools/record_fixture.py`), and each view's observations, to check the file against."""

from pathlib import Path

import pytest
from s2clientprotocol import sc2api_pb2
from sc2nachos import open_replay_recording

from salsa_reading import SalsaFile, observations_by_step
from sc2salsa._writer import write_from_playbacks

FIXTURES_FOLDER = Path(__file__).parent / "fixtures"
FIXTURE_REPLAY = FIXTURES_FOLDER / "pylon-scout-90s.SC2Replay"
FIXTURE_VIEWS = (FIXTURES_FOLDER / "pylon-scout-90s-player1.sc2rec", FIXTURES_FOLDER / "pylon-scout-90s-player2.sc2rec")


@pytest.fixture(scope="session")
def fixture_file(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The `.salsa` file the writer writes from the fixture's recorded views, with no game client."""
    output = tmp_path_factory.mktemp("written") / "pylon-scout-90s.salsa"
    with open_replay_recording(FIXTURE_VIEWS[0]) as first, open_replay_recording(FIXTURE_VIEWS[1]) as second:
        write_from_playbacks((first, second), FIXTURE_REPLAY.read_bytes(), output)
    return output


@pytest.fixture(scope="session")
def salsa(fixture_file: Path) -> SalsaFile:
    """The fixture's file, read back."""
    return SalsaFile.read(fixture_file)


@pytest.fixture(scope="session")
def views() -> tuple[dict[int, sc2api_pb2.ResponseObservation], dict[int, sc2api_pb2.ResponseObservation]]:
    """Player 1's and player 2's observations of the fixture's replay, each by step."""
    return (observations_by_step(FIXTURE_VIEWS[0]), observations_by_step(FIXTURE_VIEWS[1]))
