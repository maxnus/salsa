"""Writing a replay's `.salsa` file: playing it back as each player at once, fog on, and turning what each player's
view reports at every step into the file's tables."""

import json
import os
import zipfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow
from s2clientprotocol import sc2api_pb2
from sc2nachos.run import Installation, ReplayPlayback, open_replay

from sc2salsa.__about__ import __version__
from sc2salsa._game_facts import game_json, map_table, names_json
from sc2salsa._game_recorder import GameRecorder
from sc2salsa._parquet import parquet_bytes
from sc2salsa._schema import MEMBERS

# How each table's rows are ordered, the first column most significant, as `SPEC.md` gives it.
_SORTED_BY = {
    "map.parquet": ("x", "y"),
    "roster.parquet": ("unit",),
    "units_snapshots.parquet": ("step", "unit"),
    "units_changes.parquet": ("unit", "step"),
    "sight.parquet": ("unit", "step"),
    "orders.parquet": ("unit", "step"),
    "buffs.parquet": ("unit", "step"),
    "passengers.parquet": ("unit", "step"),
    "rallies.parquet": ("unit", "step"),
    "events.parquet": ("step", "unit"),
    "actions.parquet": ("step", "player"),
    "economy.parquet": ("player", "step"),
    "upgrades.parquet": ("player", "step"),
}


def write_salsa_file(replay: Path | str, output: Path | str, *, installation: Installation | None = None) -> None:
    """Play back the replay in the file `replay` as each of its two players at once, with the fog on, and write the
    game to `output`, a `.salsa` file as `SPEC.md` describes it.

    Two game clients run at once, each on the replay's own build with its map, as `sc2nachos.open_replay` starts
    them. Raises `FileNotFoundError` before they start if `output` is in no folder that exists, `IsADirectoryError` if
    it names a folder, and `ValueError` for a replay of other than two players. `output` is written whole or not at all.
    """
    replay_path = Path(replay)
    output_path = Path(output)
    if not output_path.parent.is_dir():
        raise FileNotFoundError(f"there is no folder {output_path.parent} to write {output_path.name} into")
    if output_path.is_dir():
        raise IsADirectoryError(f"{output_path} is a folder, not a file to write the game to")
    with (
        open_replay(replay_path, player_id=1, installation=installation) as first,
        open_replay(replay_path, player_id=2, installation=installation) as second,
    ):
        write_from_playbacks((first, second), replay_path.read_bytes(), output_path)


def write_from_playbacks(playbacks: Sequence[ReplayPlayback], replay_data: bytes, output: Path) -> None:
    """Write the game `playbacks`, player 1's and player 2's views of the replay `replay_data`, both at its start, play
    back to `output`, stepping both to the replay's end."""
    info = playbacks[0].info
    _check_two_players(info)
    game_infos = [playback.client.game_info() for playback in playbacks]
    game_data = playbacks[0].client.game_data()
    tables = {"map.parquet": map_table(game_infos[0]), **_recorded_to_the_end(playbacks).tables()}
    members = {
        "game.json": _json_bytes(game_json(info, game_infos, written_by=f"sc2salsa {__version__}")),
        "replay.SC2Replay": replay_data,
        "names.json": _json_bytes(names_json(game_data, _ids_held(tables))),
        **{name: parquet_bytes(table, sorted_by=_SORTED_BY[name]) for name, table in tables.items()},
    }
    _write_zip(output, members)


def _recorded_to_the_end(playbacks: Sequence[ReplayPlayback]) -> GameRecorder:
    """Every step of `playbacks`, from the start to the replay's end, recorded. Both clients are asked at once, each
    from a thread of its own, so that both games work at the same time: a 31-minute game's 41,416 steps took 152 s to
    play and record so, against 240 s one client after the other (salsa#4)."""
    recorder = GameRecorder()
    with ThreadPoolExecutor(max_workers=len(playbacks), thread_name_prefix="salsa-view") as clients:
        while True:
            observations = list(clients.map(_observation_of, playbacks))
            steps = {observation.observation.game_loop for observation in observations}
            if len(steps) != 1:
                raise RuntimeError(f"the players' views of the replay stand at different steps, {sorted(steps)}")
            recorder.add_step(steps.pop(), observations)
            if not all(playback.client.in_game for playback in playbacks):
                return recorder
            list(clients.map(_step_once, playbacks))


def _observation_of(playback: ReplayPlayback) -> sc2api_pb2.ResponseObservation:
    return playback.client.observation()


def _step_once(playback: ReplayPlayback) -> None:
    playback.client.step(1)


def _check_two_players(info: sc2api_pb2.ResponseReplayInfo) -> None:
    """Raise `ValueError` unless the replay `info` describes is one of players 1 and 2, observers aside."""
    players = sorted(
        entry.player_info.player_id
        for entry in info.player_info
        if entry.player_info.type != sc2api_pb2.PlayerType.Observer
    )
    if players != [1, 2]:
        raise ValueError(f"a .salsa file holds a game of players 1 and 2, and this replay's players are {players}")


def _ids_held(tables: dict[str, pyarrow.Table]) -> dict[str, set[int]]:
    """The game's ids of each kind `tables` hold, for `names.json` to name."""

    def unique(*columns: tuple[str, str]) -> set[int]:
        values: set[int] = set()
        for member, column in columns:
            values.update(value for value in tables[member].column(column).unique().to_pylist() if value is not None)
        return values

    return {
        "unit_types": unique(
            ("roster.parquet", "first_type"), ("units_snapshots.parquet", "type"), ("units_changes.parquet", "type")
        ),
        "abilities": unique(("orders.parquet", "ability"), ("actions.parquet", "ability")),
        "buffs": unique(("buffs.parquet", "buff")),
        "upgrades": unique(("upgrades.parquet", "upgrade")),
    }


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2).encode("utf-8")


def _write_zip(output: Path, members: dict[str, bytes]) -> None:
    """Write `members` to `output` as an uncompressed zip, in the order `MEMBERS` gives, through a file beside it
    renamed into place, so that `output` is whole or not written at all."""
    partial = output.with_name(f"{output.name}.partial")
    try:
        with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in MEMBERS:
                archive.writestr(name, members[name])
        os.replace(partial, output)
    finally:
        partial.unlink(missing_ok=True)
