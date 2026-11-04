"""What a `.salsa` file says of the game as a whole: `game.json`, `names.json` and the map's tiles."""

from collections.abc import Iterable, Mapping, Sequence
from pathlib import PureWindowsPath

import numpy
import pyarrow
from s2clientprotocol import common_pb2, sc2api_pb2

from sc2salsa._schema import FORMAT_VERSION, MAP, SNAPSHOT_EVERY

_RACES = {
    common_pb2.Terran: "terran",
    common_pb2.Zerg: "zerg",
    common_pb2.Protoss: "protoss",
    common_pb2.Random: "random",
}
_RESULTS = {
    sc2api_pb2.Victory: "victory",
    sc2api_pb2.Defeat: "defeat",
    sc2api_pb2.Tie: "tie",
    sc2api_pb2.Undecided: "undecided",
}


def game_json(
    info: sc2api_pb2.ResponseReplayInfo, game_infos: Sequence[sc2api_pb2.ResponseGameInfo], *, written_by: str
) -> dict[str, object]:
    """`game.json`: the replay's facts as `info` gives them, and the map's as each player's `game_infos` at the start
    give them."""
    start = game_infos[0].start_raw
    return {
        "format_version": FORMAT_VERSION,
        "written_by": written_by,
        "map_name": info.map_name,
        # A replay played on Windows names its map with backslashes, which a Windows path reads on every platform.
        "map_file": PureWindowsPath(info.local_map_path).name,
        "base_build": info.base_build,
        "data_version": info.data_version,
        "steps": info.game_duration_loops,
        "players": [_player_facts(entry) for entry in sorted(info.player_info, key=_player_id_of)],
        "map": {
            "width": start.map_size.x,
            "height": start.map_size.y,
            "playable": [
                start.playable_area.p0.x,
                start.playable_area.p0.y,
                start.playable_area.p1.x,
                start.playable_area.p1.y,
            ],
            "start_locations": _start_locations(game_infos),
        },
        "snapshot_every": SNAPSHOT_EVERY,
    }


def _player_id_of(entry: sc2api_pb2.PlayerInfoExtra) -> int:
    return entry.player_info.player_id


def _player_facts(entry: sc2api_pb2.PlayerInfoExtra) -> dict[str, object]:
    player = entry.player_info
    return {
        "player_id": player.player_id,
        "race_requested": _RACES.get(player.race_requested),
        "race_actual": _RACES.get(player.race_actual) if player.HasField("race_actual") else None,
        "result": _RESULTS.get(entry.player_result.result) if entry.player_result.HasField("result") else None,
        "apm": entry.player_apm if entry.HasField("player_apm") else None,
    }


def _start_locations(game_infos: Sequence[sc2api_pb2.ResponseGameInfo]) -> list[list[float]]:
    """The start locations each player's game info gives, each once: a player's lists the others', so on a map of two,
    player 2's names player 1's start and comes first."""
    locations: list[list[float]] = []
    for game_info in reversed(game_infos):
        for location in game_info.start_raw.start_locations:
            if [location.x, location.y] not in locations:
                locations.append([location.x, location.y])
    return locations


def names_json(data: sc2api_pb2.ResponseData, ids: Mapping[str, Iterable[int]]) -> dict[str, dict[str, str]]:
    """`names.json`: the name `data`, the game's tables at its start, gives each of `ids`, the ids of each kind the
    file holds, by `unit_types`, `abilities`, `buffs` and `upgrades`, an id the tables do not name left out."""
    tables = {
        "unit_types": {entry.unit_id: entry.name for entry in data.units},
        "abilities": {entry.ability_id: entry.friendly_name for entry in data.abilities},
        "buffs": {entry.buff_id: entry.name for entry in data.buffs},
        "upgrades": {entry.upgrade_id: entry.name for entry in data.upgrades},
    }
    return {
        kind: {str(id_): table[id_] for id_ in sorted(set(ids.get(kind, ()))) if table.get(id_)}
        for kind, table in tables.items()
    }


def map_table(game_info: sc2api_pb2.ResponseGameInfo) -> pyarrow.Table:
    """`map.parquet`: each tile of the map, by `x`, then `y`, as `game_info` at the start gives it."""
    start = game_info.start_raw
    width, height = start.map_size.x, start.map_size.y
    xs, ys = numpy.meshgrid(numpy.arange(width), numpy.arange(height), indexing="ij")
    columns = {
        "x": xs.ravel(),
        "y": ys.ravel(),
        "pathable": _image_by_tile(start.pathing_grid, width, height).ravel() != 0,
        "placeable": _image_by_tile(start.placement_grid, width, height).ravel() != 0,
        # A byte is an eighth of a unit of height, 127 at zero, at the tile's lower left corner.
        "height": (_image_by_tile(start.terrain_height, width, height).ravel().astype(numpy.float32) - 127) / 8,
    }
    return pyarrow.Table.from_pydict(columns, schema=MAP)


def _image_by_tile(image: common_pb2.ImageData, width: int, height: int) -> numpy.ndarray:
    """`image`, a grid the game sends of `width` by `height` tiles, indexed `[x, y]`. Raises `ValueError` for one of
    another size."""
    if (image.size.x, image.size.y) != (width, height) or image.bits_per_pixel not in (1, 8):
        raise ValueError(f"a {image.size.x} by {image.size.y} image of {image.bits_per_pixel} bits is no map grid")
    values = numpy.frombuffer(image.data, dtype=numpy.uint8)
    if image.bits_per_pixel == 1:
        values = numpy.unpackbits(values, count=width * height)
    # Each row is one y, from the bottom of the map up.
    return values.reshape(height, width).T
