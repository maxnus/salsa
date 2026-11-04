"""Reading a `.salsa` file back as the tests do: its members, and every unit at each step rebuilt from the snapshots
and the changes, as `SPEC.md` says a reader does."""

import json
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow
import pyarrow.parquet
from s2clientprotocol import sc2api_pb2
from sc2nachos.protocol import Recording


@dataclass(frozen=True)
class SalsaFile:
    """A `.salsa` file's members, read whole."""

    member_names: list[str]
    stored: bool
    game: dict[str, Any]
    names: dict[str, dict[str, str]]
    replay: bytes
    tables: dict[str, pyarrow.Table]

    @classmethod
    def read(cls, path: Path) -> "SalsaFile":
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            # Through pyarrow's own buffer: pyarrow 26.0.1 hangs Python 3.13 at its exit once a table is read from an
            # io.BytesIO with threads.
            tables = {
                info.filename: pyarrow.parquet.read_table(pyarrow.BufferReader(archive.read(info.filename)))
                for info in infos
                if info.filename.endswith(".parquet")
            }
            return cls(
                member_names=[info.filename for info in infos],
                stored=all(info.compress_type == zipfile.ZIP_STORED for info in infos),
                game=json.loads(archive.read("game.json")),
                names=json.loads(archive.read("names.json")),
                replay=archive.read("replay.SC2Replay"),
                tables=tables,
            )

    def rows(self, member: str) -> list[dict[str, Any]]:
        """Every row of the table `member`, each by column."""
        return self.tables[member].to_pylist()


def units_at_each_step(salsa: SalsaFile, last_step: int) -> Iterator[tuple[int, dict[int, dict[str, Any]]]]:
    """Every unit listed at each step from 0 to `last_step`, each its row by unit, rebuilt from the snapshot at or
    before the step and the changes after it, as `SPEC.md` says."""
    snapshots: dict[int, dict[int, dict[str, Any]]] = defaultdict(dict)
    for row in salsa.rows("units_snapshots.parquet"):
        snapshots[row.pop("step")][row.pop("unit")] = row
    changes: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in salsa.rows("units_changes.parquet"):
        changes[row["step"]].append(row)
    listed: dict[int, dict[str, Any]] = {}
    for step in range(last_step + 1):
        if step in snapshots:
            listed = dict(snapshots[step])
        for change in changes.get(step, ()):
            unit = change.pop("unit")
            change.pop("step")
            if change.pop("listed"):
                listed[unit] = change
            else:
                listed.pop(unit, None)
        yield step, listed


def observations_by_step(recording: Path) -> dict[int, sc2api_pb2.ResponseObservation]:
    """Each observation a recorded playback answered, by its step, the last where the game was asked twice at its
    end."""
    return {
        exchange.response.observation.observation.game_loop: exchange.response.observation
        for exchange in Recording(recording)
        if exchange.response.HasField("observation")
    }
