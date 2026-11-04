"""`actions.parquet`, `economy.parquet` and `upgrades.parquet`: what each player's own view reports of the player."""

from collections.abc import Sequence

import pyarrow
from s2clientprotocol import sc2api_pb2

from sc2salsa._player_view import PlayerView
from sc2salsa._schema import ACTIONS_SCHEMA, ECONOMY_SCHEMA, PLAYER_COMMON_FIELDS, SCORE_DETAIL_PATHS, UPGRADES_SCHEMA
from sc2salsa._table_builder import TableBuilder
from sc2salsa._unit_rows import position_of


class PlayerTables:
    """Each player's actions, at the step the game ran each on, and economy and upgrades, at the steps they change."""

    def __init__(self) -> None:
        self._actions = TableBuilder(ACTIONS_SCHEMA)
        self._economy = TableBuilder(ECONOMY_SCHEMA)
        self._upgrades = TableBuilder(UPGRADES_SCHEMA)
        self._economy_before: dict[int, tuple[object, ...]] = {}
        self._upgrades_before: dict[int, set[int]] = {}

    def add_step(self, step: int, view: PlayerView) -> None:
        """What `view`'s observation at `step` reports of its player."""
        player = view.player_id
        for action in view.observation.actions:
            row = _action_row(action, view)
            if row is not None:
                self._actions.add((action.game_loop, player, *row))
        observation = view.observation.observation
        economy = _economy_row(observation)
        if self._economy_before.get(player) != economy:
            self._economy_before[player] = economy
            self._economy.add((step, player, *economy))
        upgrades_before = self._upgrades_before.setdefault(player, set())
        for upgrade in observation.raw_data.player.upgrade_ids:
            if upgrade not in upgrades_before:
                upgrades_before.add(upgrade)
                self._upgrades.add((step, player, upgrade))

    def tables(self) -> dict[str, pyarrow.Table]:
        """The three tables, by member name, in the order their rows were added: by step. `SPEC.md` sorts actions by
        step, then player, and economy and upgrades by player, then step."""
        return {
            "actions.parquet": self._actions.table(),
            "economy.parquet": self._economy.table(),
            "upgrades.parquet": self._upgrades.table(),
        }


def _action_row(action: sc2api_pb2.Action, view: PlayerView) -> tuple[object, ...] | None:
    """`action`'s row after its step and player, if it is a command or an autocast switched: its ability, units,
    target and whether it was queued or an autocast. `None` for another kind, as a camera moved."""
    if not action.HasField("action_raw"):
        return None
    raw = action.action_raw
    if raw.HasField("unit_command"):
        command = raw.unit_command
        target_unit = view.unit_of(command.target_unit_tag) if command.HasField("target_unit_tag") else None
        if command.HasField("target_world_space_pos"):
            target = command.target_world_space_pos
            target_x, target_y = position_of(target.x), position_of(target.y)
        else:
            target_x = target_y = None
        units = [view.unit_of(tag) for tag in command.unit_tags]
        return (command.ability_id, units, target_unit, target_x, target_y, command.queue_command, False)
    if raw.HasField("toggle_autocast"):
        toggle = raw.toggle_autocast
        return (toggle.ability_id, [view.unit_of(tag) for tag in toggle.unit_tags], None, None, None, None, True)
    return None


def _economy_row(observation: sc2api_pb2.Observation) -> tuple[object, ...]:
    """The player common fields, the score and every score detail `observation` reports."""
    common = observation.player_common
    details = observation.score.score_details
    return (
        *[getattr(common, name) for name in PLAYER_COMMON_FIELDS],
        observation.score.score,
        *[_value_at(details, path) for path in SCORE_DETAIL_PATHS],
    )


def _value_at(message: object, path: Sequence[str]) -> object:
    for name in path:
        message = getattr(message, name)
    return message
