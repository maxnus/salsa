"""One player's playback of the replay, fog on: what it lists at a step, and the unit each entry names."""

from s2clientprotocol import raw_pb2, sc2api_pb2

from sc2salsa._roster import MAP_OWNER, Roster, Spot

_VISIBLE = raw_pb2.DisplayType.Visible
_COPY = raw_pb2.DisplayType.Snapshot
_UNDETECTED = raw_pb2.DisplayType.Hidden
_OWN = raw_pb2.Alliance.Self

# A player's sight of a unit, as `SIGHT_WORDS` indexes them; the higher wins where a view lists a unit twice.
SIGHT_OUT, SIGHT_REMEMBERED, SIGHT_UNDETECTED, SIGHT_SEEN = range(4)
_SIGHT_OF_DISPLAY = {_VISIBLE: SIGHT_SEEN, _UNDETECTED: SIGHT_UNDETECTED, _COPY: SIGHT_REMEMBERED}


def spot_of(entry: raw_pb2.Unit) -> Spot:
    """Where `entry` stands, with its type."""
    return (entry.unit_type, entry.pos.x, entry.pos.y)


def is_own_unit(entry: raw_pb2.Unit) -> bool:
    """Whether `entry` is one of the player's own units in its own view, rather than a copy or another's."""
    return entry.alliance == _OWN and entry.display_type == _VISIBLE


class PlayerView:
    """The playback as `player_id` saw the game: the entries it lists at the step read last, by tag, each naming a
    unit of `roster`. An entry the game lists with no tag, a placeholder or a radar blip, is not a unit."""

    def __init__(self, player_id: int, roster: Roster) -> None:
        self.player_id = player_id
        self.observation = sc2api_pb2.ResponseObservation()
        self.entries: dict[int, raw_pb2.Unit] = {}
        self._roster = roster
        self._came: list[raw_pb2.Unit] = []
        self._gone_unit_at_spot: dict[Spot, int] = {}

    def read(self, observation: sc2api_pb2.ResponseObservation) -> None:
        """Take the step's `observation`: what the view lists now, and what came into the list and left it since the
        step before."""
        entries = {entry.tag: entry for entry in observation.observation.raw_data.units if entry.tag}
        unit_of_tag = self._roster.unit_of_tag
        gone_unit_at_spot = {}
        for tag, entry in self.entries.items():
            if tag not in entries and (unit := unit_of_tag.get(tag)) is not None:
                gone_unit_at_spot[spot_of(entry)] = unit
        self._came = [entry for tag, entry in entries.items() if tag not in self.entries]
        self._gone_unit_at_spot = gone_unit_at_spot
        self.entries = entries
        self.observation = observation

    def name_own_units(self, step: int) -> None:
        """Name the unit of each of the player's own entries that came into the list at `step`, a new one where none
        is named yet: a unit is first listed by its owner's view, which reports it in full."""
        for entry in self._came:
            if is_own_unit(entry):
                self._name(entry, step)

    def name_other_units(self, step: int) -> None:
        """Name the unit of each other entry that came into the list at `step`: another player's, which its owner's
        view names, a copy in the fog, or the map's, a new map unit where none is named yet."""
        for entry in self._came:
            if not is_own_unit(entry):
                self._name(entry, step)

    def unit_of(self, tag: int) -> int | None:
        """The unit `tag` names, as an order or an action gives it: a unit's own tag, or a copy's this view or the other
        listed. `None` for a tag no view listed."""
        return self._roster.unit_of_tag.get(tag) if tag else None

    def sight(self) -> dict[int, int]:
        """The player's sight of each unit the view lists at the step read last, as `SIGHT_WORDS` indexes it."""
        unit_of_tag = self._roster.unit_of_tag
        sight: dict[int, int] = {}
        for tag, entry in self.entries.items():
            unit = unit_of_tag.get(tag)
            if unit is not None:
                seen_as = _SIGHT_OF_DISPLAY.get(entry.display_type, SIGHT_OUT)
                if seen_as > sight.get(unit, SIGHT_OUT):
                    sight[unit] = seen_as
        return sight

    def _name(self, entry: raw_pb2.Unit, step: int) -> None:
        roster = self._roster
        if entry.tag in roster.unit_of_tag:
            return
        is_copy = entry.display_type == _COPY
        spot = spot_of(entry)
        is_map_unit = entry.owner == MAP_OWNER
        # The unit it replaced as it came into sight or left it, of its type at its very position (in game).
        unit = self._gone_unit_at_spot.get(spot)
        if unit is None and is_map_unit:
            unit = roster.map_unit_at(spot)
        if unit is not None:
            roster.name(unit, entry.tag, is_copy=is_copy)
            return
        if not (is_map_unit or is_own_unit(entry)):
            # Another player's unit its owner's view never listed, or a copy of one no view named: not a unit.
            return
        unit = roster.add(
            tag=None if is_copy else entry.tag,
            copy_tag=entry.tag if is_copy else None,
            owner=entry.owner,
            unit_type=entry.unit_type,
            step=step,
        )
        if is_map_unit:
            roster.place_map_unit(unit, spot)
