"""Tests for combat start in loop.py — O1/O2/O3/O4.

Covered:
- _start_combat: writes hidden["combat"], sets current_mode, returns report.
- Movement roll (§10): 1-2 fail (stay), 3-6 pass.
- On-entry encounter (§23, O1): dangerous 1-2 attack, 3-6 quiet;
  thicket -> ambush; safe -> no encounter.
- New node generation via world.enter_node (§17).
- Combat report appears in events on start.
- O4 deferred: no attack_* in exploring menu.

All docstrings/comments in English. No Cyrillic literals.
"""

import pytest

from burt.loop import (
    Action, ActionResult, build_menu, execute_action,
    _start_combat, _maybe_start_combat_on_enter,
    _enter_new_node, _handle_movement_failure,
)
from burt.combat import start_combat
from burt.bestiary import ENEMIES


# ─── Helpers ───────────────────────────────────────────────

def make_state():
    """Base state: exploring, world-graph start, ready for go_."""
    from burt import world
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": "1 день",
            "effects": [],
            "location": {
                "name": "Crossroads",
                "exits": ["north", "east", "south", "west"],
            },
            "inventory": [], "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
        },
        "hidden": {
            "current_mode": "exploring",
            "current_node_id": "start",
            "location_graph": world.create_start_graph(),
            "combat": None,
            "hp_raw": 10, "mp_raw": 3,
            "spells": {"element": None, "alignment": None},
            "step": 0, "day": 1,
        },
    }


def _seq_rng(values):
    """rng returning values in order; stays on the last one.

    Values must be non-empty. Each call advances, last value repeats.
    """
    values = list(values)
    if not values:
        raise ValueError("_seq_rng needs at least one value")
    state = {"i": 0}

    def _rng():
        i = min(state["i"], len(values) - 1)
        state["i"] += 1
        return values[i]

    return _rng


def _start_node_exits(st):
    """Convenience: get exit -> id mapping of the start node."""
    return st["hidden"]["location_graph"]["start"]["exits"]


# ─── TestStartCombat ───────────────────────────────────────

class TestStartCombat:
    def test_writes_hidden_combat(self):
        st = make_state()
        _start_combat(["wolf"], "enemy", st["hidden"], st["visible"])
        assert st["hidden"]["combat"] is not None
        assert st["hidden"]["combat"]["enemies"][0]["key"] == "wolf"

    def test_sets_current_mode_combat(self):
        st = make_state()
        _start_combat(["wolf"], "enemy", st["hidden"], st["visible"])
        assert st["hidden"]["current_mode"] == "combat"

    def test_returns_combat_report(self):
        st = make_state()
        report = _start_combat(
            ["wolf"], "enemy", st["hidden"], st["visible"],
        )
        assert isinstance(report, str)
        assert "[БОЙ]" in report
        assert "волк" in report.lower()

    def test_initiative_enemy_preserved(self):
        st = make_state()
        _start_combat(["wolf"], "enemy", st["hidden"], st["visible"])
        assert st["hidden"]["combat"]["initiative"] == "enemy"
        # enemy initiative -> free strike not yet done.
        assert st["hidden"]["combat"]["free_strike_done"] is False

    def test_initiative_burt_preserved(self):
        st = make_state()
        _start_combat(["wolf"], "burt", st["hidden"], st["visible"])
        assert st["hidden"]["combat"]["initiative"] == "burt"
        assert st["hidden"]["combat"]["free_strike_done"] is True

    def test_empty_enemy_keys_raises(self):
        st = make_state()
        with pytest.raises(ValueError):
            _start_combat([], "enemy", st["hidden"], st["visible"])


# ─── TestMovementRoll ──────────────────────────────────────

class TestMovementRoll:
    # Start node has preset neighbours (all typed, entered=False):
    #   north -> дорога, east -> кустарник, south -> лес, west -> река.
    # We use north (дорога) here: safe -> no encounter on entry.

    def test_roll_1_stays_in_place(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([1]),
        )
        assert st["hidden"]["current_node_id"] == "start"
        assert st["hidden"]["step"] == 1

    def test_roll_2_stays_in_place(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([2]),
        )
        assert st["hidden"]["current_node_id"] == "start"
        assert st["hidden"]["step"] == 1

    def test_roll_3_moves(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([3, 4, 4, 4, 4]),
        )
        assert st["hidden"]["current_node_id"] != "start"

    def test_roll_4_moves(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([4, 4, 4, 4, 4]),
        )
        assert st["hidden"]["current_node_id"] != "start"

    def test_roll_5_moves(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([5, 4, 4, 4, 4]),
        )
        assert st["hidden"]["current_node_id"] != "start"

    def test_roll_6_moves(self):
        st = make_state()
        execute_action(
            Action("go_north", "Go"), st,
            rng=_seq_rng([6, 4, 4, 4, 4]),
        )
        assert st["hidden"]["current_node_id"] != "start"


# ─── TestOnEntryEncounter ──────────────────────────────────

class TestOnEntryEncounter:
    # South -> лес (dangerous). rng seq:
    #   [move, count, dirs, type, size, encounter_roll, ...]
    # East -> кустарник (ambush). rng seq:
    #   [move, count, dirs, type, size, ambush_type, ambush_size]

    def test_forest_encounter_roll_1_starts_combat(self):
        st = make_state()
        # move=4, node rolls=4,4,4,4, encounter=1 -> attack,
        # spawn_random: type=4 (wolf), size=6 (1 wolf).
        rng = _seq_rng([4, 4, 4, 4, 4, 1, 4, 6])
        result = execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "combat"
        assert st["hidden"]["combat"] is not None
        assert st["hidden"]["combat"]["initiative"] == "enemy"
        assert any("[БОЙ]" in ev for ev in result.events)

    def test_forest_encounter_roll_2_starts_combat(self):
        st = make_state()
        rng = _seq_rng([4, 4, 4, 4, 4, 2, 4, 6])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "combat"

    def test_forest_encounter_roll_3_quiet(self):
        st = make_state()
        rng = _seq_rng([4, 4, 4, 4, 4, 3])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "exploring"
        assert st["hidden"]["combat"] is None

    def test_forest_encounter_roll_4_quiet(self):
        st = make_state()
        rng = _seq_rng([4, 4, 4, 4, 4, 4])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "exploring"

    def test_thicket_always_ambush(self):
        st = make_state()
        # move=4, node rolls=4,4,4,4, ambush: type=1 (wolf), size=1 (3 wolves).
        rng = _seq_rng([4, 4, 4, 4, 4, 1, 1])
        result = execute_action(Action("go_east", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "combat"
        assert st["hidden"]["combat"]["initiative"] == "enemy"
        assert len(st["hidden"]["combat"]["enemies"]) == 3
        assert any("[БОЙ]" in ev for ev in result.events)

    def test_river_no_encounter(self):
        """River is safe: _maybe_start_combat_on_enter returns None."""
        st = make_state()
        result = _maybe_start_combat_on_enter(
            "река", st["hidden"], st["visible"], lambda: 1,
        )
        assert result is None
        assert st["hidden"]["current_mode"] == "exploring"
        assert st["hidden"]["combat"] is None

    def test_village_no_encounter(self):
        st = make_state()
        result = _maybe_start_combat_on_enter(
            "деревня", st["hidden"], st["visible"], lambda: 1,
        )
        assert result is None
        assert st["hidden"]["current_mode"] == "exploring"


# ─── TestNewNodeGeneration ─────────────────────────────────

class TestNewNodeGeneration:
    def test_new_node_gets_type(self):
        st = make_state()
        south_id = _start_node_exits(st)["south"]
        st["hidden"]["location_graph"][south_id]["type"] = None
        # move=4, count=4, dirs=4, type=1 (лес), size=4, encounter=3.
        rng = _seq_rng([4, 4, 4, 1, 4, 3])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["location_graph"][south_id]["type"] == "лес"

    def test_new_node_gets_exits(self):
        st = make_state()
        south_id = _start_node_exits(st)["south"]
        st["hidden"]["location_graph"][south_id]["type"] = None
        # count=6 -> 4 exits (all directions); back edge (south) is
        # already occupied -> only 3 new neighbours get linked.
        rng = _seq_rng([4, 6, 1, 1, 4, 3])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        node = st["hidden"]["location_graph"][south_id]
        linked = [d for d, t in node["exits"].items() if t]
        assert len(linked) >= 2  # back edge + at least one new

    def test_enter_new_node_raises_on_already_entered(self):
        st = make_state()
        graph = st["hidden"]["location_graph"]
        start_node = graph["start"]
        assert start_node["entered"] is True
        with pytest.raises(ValueError):
            _enter_new_node(graph, "start", lambda: 4)

    def test_enter_new_node_with_roll_type_5_does_not_crash(self):
        """roll_type=5 needs roll_size in 1..3; our helper normalizes."""
        st = make_state()
        graph = st["hidden"]["location_graph"]
        south_id = _start_node_exits(st)["south"]
        # Reset node to be new.
        graph[south_id]["type"] = None
        graph[south_id]["entered"] = False
        # rng: count=4, dirs=4, type=5, size_roll=4 -> normalized to 1..3.
        rng = _seq_rng([4, 4, 5, 4])
        _enter_new_node(graph, south_id, rng)
        assert graph[south_id]["type"] in ("болото", "река", "дорога")
        assert graph[south_id]["entered"] is True


# ─── TestCombatReportInEvents ──────────────────────────────

class TestCombatReportInEvents:
    def test_events_contain_combat_report_on_start(self):
        st = make_state()
        # South -> лес, encounter roll=1.
        rng = _seq_rng([4, 4, 4, 4, 4, 1, 4, 6])
        result = execute_action(Action("go_south", "Go"), st, rng=rng)
        combat_events = [ev for ev in result.events if "[БОЙ]" in ev]
        assert len(combat_events) == 1

    def test_combat_mode_persists_after_attack(self):
        st = make_state()
        rng = _seq_rng([4, 4, 4, 4, 4, 1, 4, 6])
        execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "combat"
        # One round of block (rng=5: enemy misses) -> still combat.
        execute_action(Action("block", "Block"), st, rng=lambda: 5)
        assert st["hidden"]["current_mode"] == "combat"


# ─── TestTodos ─────────────────────────────────────────────

class TestTodos:
    def test_no_attack_in_exploring_menu(self):
        """O4 deferred: Burt does not initiate combat from exploring."""
        st = make_state()
        keys = [a.key for a in build_menu(st["visible"], st)]
        assert not any(k.startswith("attack_") for k in keys)

    def test_movement_failure_returns_result_and_increments_step(self):
        st = make_state()
        result = _handle_movement_failure("north", "fail", st["hidden"])
        assert isinstance(result, ActionResult)
        assert st["hidden"]["step"] == 1
        assert len(result.events) >= 1

    def test_movement_failure_bad_returns_result(self):
        st = make_state()
        result = _handle_movement_failure("north", "fail_bad", st["hidden"])
        assert isinstance(result, ActionResult)
        assert st["hidden"]["step"] == 1