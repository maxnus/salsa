"""The file the writer writes from the recorded fixture, with no game client, checked against `SPEC.md` and against
what each player's view reported at every step."""

from collections import Counter
from pathlib import Path
from typing import Any

import numpy
import pyarrow
import pytest
from s2clientprotocol import raw_pb2, sc2api_pb2, score_pb2
from sc2nachos.protocol import Recording

from conftest import FIXTURE_REPLAY, FIXTURE_VIEWS
from salsa_reading import SalsaFile, units_at_each_step
from sc2salsa._writer import _check_two_players, write_salsa_file
from spec_tables import SCORE_DETAILS, WORDS, spec_columns, spec_members

type Views = tuple[dict[int, sc2api_pb2.ResponseObservation], dict[int, sc2api_pb2.ResponseObservation]]

_VISIBLE = raw_pb2.DisplayType.Visible
_UNDETECTED = raw_pb2.DisplayType.Hidden
_OWN = raw_pb2.Alliance.Self
_MAP_OWNER = 16

# Each unit table column the entry's field of the same meaning gives, where the two names differ.
_FIELD_OF_COLUMN = {
    "type": "unit_type",
    "flying": "is_flying",
    "burrowed": "is_burrowed",
    "hallucination": "is_hallucination",
    "powered": "is_powered",
    "active": "is_active",
    "attack_level": "attack_upgrade_level",
    "armor_level": "armor_upgrade_level",
    "shield_level": "shield_upgrade_level",
    "minerals": "mineral_contents",
    "vespene": "vespene_contents",
    "cargo_used": "cargo_space_taken",
    "cargo_max": "cargo_space_max",
}
# Columns worked out from more than one field, or naming units: compared on their own.
_WORKED_OUT = {"x", "y", "buff_duration_left", "buff_duration_max", "add_on", "engaged_target"}


@pytest.fixture(scope="module")
def listed_at_each_step(salsa: SalsaFile, views: Views) -> list[dict[int, dict[str, Any]]]:
    """Every unit listed at each step of the fixture, rebuilt from the snapshots and the changes."""
    last_step = max(views[0])
    return [dict(listed) for _, listed in units_at_each_step(salsa, last_step)]


@pytest.fixture(scope="module")
def unit_of_tag(salsa: SalsaFile) -> dict[int, int]:
    """Each unit the roster gives a tag, by its tag."""
    return {row["tag"]: row["unit"] for row in salsa.rows("roster.parquet") if row["tag"] is not None}


def _expected_row(entry: raw_pb2.Unit, unit_of_tag: dict[int, int]) -> dict[str, Any]:
    """The row `SPEC.md` says `entry` makes, read field by field, apart from the writer's own reading."""
    row: dict[str, Any] = {}
    for column, _ in spec_columns()["units_snapshots.parquet"][2:]:
        if column not in _WORKED_OUT:
            field = _FIELD_OF_COLUMN.get(column, column)
            # Named by a string here, which protobuf's stubs type as each field's literal name.
            has_field = entry.HasField(field)  # pyright: ignore[reportArgumentType]
            row[column] = getattr(entry, field) if has_field else None
    row["x"], row["y"] = round(entry.pos.x * 4096), round(entry.pos.y * 4096)
    timed = entry.HasField("buff_duration_max") and entry.buff_duration_max > 0
    row["buff_duration_left"] = entry.buff_duration_remain if timed else None
    row["buff_duration_max"] = entry.buff_duration_max if timed else None
    row["add_on"] = unit_of_tag.get(entry.add_on_tag) if entry.add_on_tag else None
    row["engaged_target"] = unit_of_tag.get(entry.engaged_target_tag) if entry.engaged_target_tag else None
    return row


def _matches(listed: dict[str, Any], entry: raw_pb2.Unit, unit_of_tag: dict[int, int]) -> bool:
    """Whether a unit's row rebuilt from the file is what `entry` reports. A target named by a copy's tag, which the
    roster does not give, is left out."""
    expected = _expected_row(entry, unit_of_tag)
    for column in ("add_on", "engaged_target"):
        tag = entry.add_on_tag if column == "add_on" else entry.engaged_target_tag
        if tag and tag not in unit_of_tag:
            expected[column] = listed[column]
    # Read back from float32, as the game reports them.
    return all(listed[column] == value for column, value in expected.items())


class TestTheFile:
    def test_its_members_are_the_specs_in_the_specs_order_and_stored(self, salsa: SalsaFile) -> None:
        assert salsa.member_names == spec_members()
        assert salsa.stored

    def test_it_keeps_the_replay_byte_for_byte(self, salsa: SalsaFile) -> None:
        assert salsa.replay == FIXTURE_REPLAY.read_bytes()

    @pytest.mark.parametrize("member", sorted(spec_columns()))
    def test_each_table_has_the_columns_and_types_the_spec_gives(self, salsa: SalsaFile, member: str) -> None:
        expected: list[tuple[str, pyarrow.DataType | str]] = []
        for name, kind in spec_columns()[member]:
            if name == SCORE_DETAILS:
                expected.extend((detail, pyarrow.float32()) for detail in _score_detail_columns())
            else:
                expected.append((name, kind))
        schema = salsa.tables[member].schema
        assert schema.names == [name for name, _ in expected]
        for (name, kind), field in zip(expected, schema, strict=True):
            if kind == WORDS:
                assert pyarrow.types.is_dictionary(field.type) and field.type.value_type == pyarrow.string(), name
            else:
                assert field.type == kind, name

    @pytest.mark.parametrize(
        ("member", "keys"),
        [
            ("map.parquet", ("x", "y")),
            ("roster.parquet", ("unit",)),
            ("units_snapshots.parquet", ("step", "unit")),
            ("units_changes.parquet", ("unit", "step")),
            ("sight.parquet", ("unit", "step")),
            ("orders.parquet", ("unit", "step", "position")),
            ("buffs.parquet", ("unit", "step")),
            ("passengers.parquet", ("unit", "step")),
            ("rallies.parquet", ("unit", "step", "position")),
            ("events.parquet", ("step", "unit")),
            ("actions.parquet", ("step", "player")),
            ("economy.parquet", ("player", "step")),
            ("upgrades.parquet", ("player", "step")),
        ],
    )
    def test_each_table_is_sorted_as_the_spec_says(self, salsa: SalsaFile, member: str, keys: tuple[str, ...]) -> None:
        table = salsa.tables[member]
        # A list's empty row has no position; it sorts first among its unit's rows at its step.
        columns = [table.column(key).cast(pyarrow.int64()).fill_null(-1).to_numpy() for key in keys]
        assert (numpy.lexsort(columns[::-1]) == numpy.arange(table.num_rows)).all()


def _score_detail_columns() -> list[str]:
    """The game's score details flattened, as `SPEC.md` names them: a category's `killed_minerals_army`."""
    columns = []
    for field in score_pb2.ScoreDetails.DESCRIPTOR.fields:
        if field.message_type is None:
            columns.append(field.name)
        else:
            columns.extend(f"{field.name}_{part.name}" for part in field.message_type.fields)
    return columns


class TestTheGamesFacts:
    def test_they_are_the_replays_and_the_maps(self, salsa: SalsaFile, views: Views) -> None:
        info = next(
            exchange.response.replay_info
            for exchange in Recording(FIXTURE_VIEWS[0])
            if exchange.response.HasField("replay_info")
        )
        game = salsa.game
        assert game["format_version"] == 1
        assert str(game["written_by"]).startswith("sc2salsa ")
        assert (game["map_name"], game["map_file"]) == ("Pylon AIE", "PylonAIE_v4.SC2Map")
        assert (game["base_build"], game["data_version"]) == (info.base_build, info.data_version)
        assert game["steps"] == info.game_duration_loops
        players = game["players"]
        assert isinstance(players, list)
        assert [(player["player_id"], player["race_requested"]) for player in players] == [(1, "terran"), (2, "zerg")]
        assert game["snapshot_every"] == 28
        game_map = game["map"]
        assert isinstance(game_map, dict)
        assert len(game_map["start_locations"]) == 2
        assert salsa.tables["map.parquet"].num_rows == game_map["width"] * game_map["height"]

    def test_every_id_the_tables_hold_is_named(self, salsa: SalsaFile) -> None:
        held = {
            "unit_types": [("roster.parquet", "first_type"), ("units_changes.parquet", "type")],
            "abilities": [("orders.parquet", "ability"), ("actions.parquet", "ability")],
            "buffs": [("buffs.parquet", "buff")],
            "upgrades": [("upgrades.parquet", "upgrade")],
        }
        for kind, columns in held.items():
            ids = {value for member, column in columns for value in salsa.tables[member].column(column).to_pylist()}
            assert {str(value) for value in ids if value is not None} <= set(salsa.names[kind]), kind


class TestTheUnits:
    def test_each_players_units_at_every_step_are_as_its_own_view_reports_them(
        self, listed_at_each_step: list[dict[int, dict[str, Any]]], views: Views, unit_of_tag: dict[int, int]
    ) -> None:
        compared = 0
        for player, view in enumerate(views, start=1):
            for step, observation in view.items():
                own = [entry for entry in observation.observation.raw_data.units if entry.alliance == _OWN]
                own = [entry for entry in own if entry.display_type == _VISIBLE]
                listed = listed_at_each_step[step]
                assert {unit for unit, row in listed.items() if row["owner"] == player} == {
                    unit_of_tag[entry.tag] for entry in own
                }, step
                for entry in own:
                    assert _matches(listed[unit_of_tag[entry.tag]], entry, unit_of_tag), (step, entry.tag)
                    compared += 1
        assert compared > 50_000

    def test_a_map_unit_in_a_players_sight_is_as_that_view_reports_it(
        self, listed_at_each_step: list[dict[int, dict[str, Any]]], views: Views, unit_of_tag: dict[int, int]
    ) -> None:
        compared = 0
        for step, listed in enumerate(listed_at_each_step):
            compared_at_step = set()
            for view in views:
                for entry in view[step].observation.raw_data.units:
                    if entry.owner != _MAP_OWNER or entry.display_type != _VISIBLE or entry.tag in compared_at_step:
                        continue
                    compared_at_step.add(entry.tag)
                    assert _matches(listed[unit_of_tag[entry.tag]], entry, unit_of_tag), (step, entry.tag)
                    compared += 1
        assert compared > 10_000

    def test_a_map_unit_is_listed_from_its_first_step_until_reported_dead(
        self, salsa: SalsaFile, listed_at_each_step: list[dict[int, dict[str, Any]]]
    ) -> None:
        died_at = {row["unit"]: row["step"] for row in salsa.rows("events.parquet") if row["kind"] == "died"}
        for row in salsa.rows("roster.parquet"):
            if row["owner"] != _MAP_OWNER:
                continue
            end = died_at.get(row["unit"], len(listed_at_each_step))
            assert all(row["unit"] in listed for listed in listed_at_each_step[row["first_step"] : end])
            assert not any(row["unit"] in listed for listed in listed_at_each_step[end:])

    def test_the_rosters_steps_are_the_first_and_the_last_each_unit_is_listed(
        self, salsa: SalsaFile, listed_at_each_step: list[dict[int, dict[str, Any]]]
    ) -> None:
        steps_listed: dict[int, list[int]] = {}
        for step, listed in enumerate(listed_at_each_step):
            for unit in listed:
                steps_listed.setdefault(unit, []).append(step)
        roster = salsa.rows("roster.parquet")
        assert [row["unit"] for row in roster] == list(range(len(roster)))
        for row in roster:
            steps = steps_listed[row["unit"]]
            assert (row["first_step"], row["last_step"]) == (steps[0], steps[-1]), row
            assert row["first_type"] == listed_at_each_step[steps[0]][row["unit"]]["type"]
        tags = [row["tag"] for row in roster if row["tag"] is not None]
        assert len(tags) == len(set(tags))

    def test_the_fixture_has_what_it_was_made_for(self, salsa: SalsaFile) -> None:
        """A map unit no player saw, the enemy's units seen and some left behind as copies."""
        roster = salsa.rows("roster.parquet")
        owners = [row["owner"] for row in roster]
        assert any(row["tag"] is None for row in roster if row["owner"] == _MAP_OWNER)
        seen = Counter((owners[row["unit"]], row["sight_1"]) for row in salsa.rows("sight.parquet"))
        assert seen[(2, "seen")] > 0 and seen[(2, "remembered")] > 0


class TestSight:
    def test_each_player_sees_what_its_view_lists_in_sight(
        self, salsa: SalsaFile, views: Views, unit_of_tag: dict[int, int]
    ) -> None:
        sight_rows: dict[int, list[dict[str, Any]]] = {}
        for row in salsa.rows("sight.parquet"):
            sight_rows.setdefault(row["step"], []).append(row)
        sight: dict[int, tuple[str, str]] = {}
        for step in range(len(views[0])):
            for row in sight_rows.get(step, ()):
                sight[row["unit"]] = (row["sight_1"], row["sight_2"])
            for player, view in enumerate(views):
                for entry in view[step].observation.raw_data.units:
                    expected = {_VISIBLE: "seen", _UNDETECTED: "undetected"}.get(entry.display_type)
                    if expected is not None and entry.tag in unit_of_tag:
                        assert sight[unit_of_tag[entry.tag]][player] == expected, (step, entry.tag)

    def test_a_unit_has_a_sight_row_at_its_first_step(self, salsa: SalsaFile) -> None:
        first_rows = {}
        for row in salsa.rows("sight.parquet"):
            first_rows.setdefault(row["unit"], row["step"])
        assert first_rows == {row["unit"]: row["first_step"] for row in salsa.rows("roster.parquet")}


class TestEvents:
    def test_each_unit_is_created_once_at_its_first_step(self, salsa: SalsaFile) -> None:
        created = [(row["step"], row["unit"]) for row in salsa.rows("events.parquet") if row["kind"] == "created"]
        assert created == sorted((row["first_step"], row["unit"]) for row in salsa.rows("roster.parquet"))

    def test_a_unit_dies_at_the_first_step_a_view_reports_it_dead(
        self, salsa: SalsaFile, views: Views, unit_of_tag: dict[int, int]
    ) -> None:
        reported: dict[int, int] = {}
        for view in views:
            for step, observation in sorted(view.items()):
                for tag in observation.observation.raw_data.event.dead_units:
                    if tag in unit_of_tag:
                        reported[unit_of_tag[tag]] = min(step, reported.get(unit_of_tag[tag], step))
        died = {row["unit"]: row["step"] for row in salsa.rows("events.parquet") if row["kind"] == "died"}
        assert died == reported


class TestEachPlayersOwnTables:
    def test_its_actions_are_the_commands_its_view_reports_at_the_step_the_game_ran_each(
        self, salsa: SalsaFile, views: Views
    ) -> None:
        """The game stamps a client's action with the step before the observation that reports it, and the built-in
        computer's, player 2 here, with the observation's own (in game)."""
        for player, view in enumerate(views, start=1):
            commands = [
                (step, action)
                for step, observation in sorted(view.items())
                for action in observation.actions
                if action.action_raw.HasField("unit_command") or action.action_raw.HasField("toggle_autocast")
            ]
            expected = [(action.game_loop, _ability_of(action)) for _, action in commands]
            actions = [
                (row["step"], row["ability"]) for row in salsa.rows("actions.parquet") if row["player"] == player
            ]
            assert actions == sorted(expected, key=lambda action: action[0])
            assert {reported - action.game_loop for reported, action in commands} == {1 if player == 1 else 0}

    def test_its_economy_at_every_step_is_as_its_view_reports_it(self, salsa: SalsaFile, views: Views) -> None:
        for player, view in enumerate(views, start=1):
            rows = {row["step"]: row for row in salsa.rows("economy.parquet") if row["player"] == player}
            assert 0 in rows
            current: dict[str, Any] = {}
            for step, observation in sorted(view.items()):
                current = rows.get(step, current)
                common = observation.observation.player_common
                assert current["minerals"] == common.minerals and current["food_used"] == common.food_used, step
                assert current["score"] == observation.observation.score.score, step


def _ability_of(action: sc2api_pb2.Action) -> int:
    """The ability of `action`, a command or an autocast switched."""
    raw = action.action_raw
    return raw.unit_command.ability_id if raw.HasField("unit_command") else raw.toggle_autocast.ability_id


class TestOrders:
    def test_each_players_units_orders_are_as_its_own_view_reports_them(
        self, salsa: SalsaFile, views: Views, unit_of_tag: dict[int, int]
    ) -> None:
        rows_by_step: dict[int, list[dict[str, Any]]] = {}
        for row in salsa.rows("orders.parquet"):
            rows_by_step.setdefault(row["step"], []).append(row)
        orders: dict[int, list[tuple[object, ...]]] = {}
        for step in range(len(views[0])):
            changed: dict[int, list[tuple[object, ...]]] = {}
            for row in rows_by_step.get(step, ()):
                items = changed.setdefault(row["unit"], [])
                if row["position"] is not None:
                    items.append((row["ability"], row["progress"]))
            orders.update(changed)
            for view in views:
                for entry in view[step].observation.raw_data.units:
                    if entry.alliance == _OWN and entry.display_type == _VISIBLE:
                        expected = [
                            (order.ability_id, order.progress if order.HasField("progress") else None)
                            for order in entry.orders
                        ]
                        assert orders.get(unit_of_tag[entry.tag], []) == expected, (step, entry.tag)


class TestRefusals:
    def test_a_replay_of_other_than_two_players_is_refused(self) -> None:
        info = sc2api_pb2.ResponseReplayInfo(
            player_info=[sc2api_pb2.PlayerInfoExtra(player_info=sc2api_pb2.PlayerInfo(player_id=1))]
        )
        with pytest.raises(ValueError, match=r"players 1 and 2, and this replay's players are \[1\]"):
            _check_two_players(info)

    @pytest.mark.parametrize(
        ("output", "error"),
        [("missing/game.salsa", FileNotFoundError), (".", IsADirectoryError)],
        ids=["in no folder", "a folder"],
    )
    def test_an_output_that_cannot_be_written_is_refused_before_a_game_starts(
        self, tmp_path: Path, output: str, error: type[OSError]
    ) -> None:
        with pytest.raises(error):
            write_salsa_file(FIXTURE_REPLAY, tmp_path / output)


@pytest.mark.integration
def test_in_a_real_game_the_file_is_the_one_its_recorded_views_make(tmp_path: Path, salsa: SalsaFile) -> None:
    """Run with `pytest -m integration`. Writes the fixture's replay from two game clients, which must give the very
    tables the recordings of them give, but for a few rows of sight: which copies a view lists at the edge of its sight
    can differ by a step from one playback to the next (in game)."""
    output = tmp_path / "pylon-scout-90s.salsa"
    write_salsa_file(FIXTURE_REPLAY, output)
    written = SalsaFile.read(output)
    assert written.member_names == salsa.member_names
    assert written.game == salsa.game
    assert written.names == salsa.names
    for member, table in salsa.tables.items():
        if member != "sight.parquet":
            assert written.tables[member].equals(table), member
    recorded_sight = {tuple(row.values()) for row in salsa.rows("sight.parquet")}
    written_sight = {tuple(row.values()) for row in written.rows("sight.parquet")}
    assert len(recorded_sight ^ written_sight) <= max(4, len(recorded_sight) // 1000)
