"""Tests for bad movement events on roll 1 (fail_bad) — §10 HANDOFF-9.5.

Covered:
- dice.resolve_bad_movement_event: trap/sprain/ambush/nothing tables.
- _handle_movement_failure: bad event applied only on fail_bad (move=1),
  NOT on fail (move=2).
- Ambush starts combat in dangerous locations, falls back to trap in safe.
- game_over=True when HP drops to 0 from micro or bad event.
- Micro-location preserved after bad-event combat.

All docstrings/comments in English. No Cyrillic literals.
"""

import pytest

from burt.loop import (
    Action, ActionResult, execute_action,
    _handle_movement_failure,
)
from burt.dice import resolve_bad_movement_event, BadMovementEventResult
from burt import world


# ─── Helpers ───────────────────────────────────────────────

def make_state():
    """Base state: exploring, world-graph start."""
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "level": 1,
            "eat": True, "sleep_counter": 5, "date": "1 день",
            "effects": [],
            "location": {
                "name": "Crossroads",
                "exits": ["north", "east", "south", "west"],
            },
            "inventory": [],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
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


def _mini_graph(node_type, exits_dict):
    """Create a minimal graph with two nodes.

    Args:
        node_type: type string for the source node (e.g. "лес").
        exits_dict: dict mapping direction -> target_node_id.

    Returns:
        Graph dict with 'source' and 'target' nodes.
    """
    return {
        "source": {
            "type": node_type,
            "entered": True,
            "exits": exits_dict,
        },
        "target": {
            "type": node_type,
            "entered": True,
            "exits": {},
        },
    }


# ─── Unit tests for dice.resolve_bad_movement_event ──────

class TestResolveBadMovementEvent:
    """Unit tests for dice.resolve_bad_movement_event()."""

    def test_trap_extra_damage(self):
        """Roll 1 → trap, extra_damage = rng() (1..6)."""
        r = resolve_bad_movement_event(1, rng=_seq_rng([3]))
        assert r.event_type == "trap"
        assert r.extra_damage == 3
        assert r.starts_combat is False
        assert r.description == "You stepped into a trap."

    def test_sprain_extra_damage_capped(self):
        """Roll 2 → sprain, extra_damage capped at 3."""
        r = resolve_bad_movement_event(2, rng=_seq_rng([5]))
        assert r.event_type == "sprain"
        assert r.extra_damage == 3  # min(5, 3)
        assert r.starts_combat is False
        assert r.description == "You twisted your ankle."

    def test_ambush_starts_combat(self):
        """Roll 3 + is_dangerous=True → ambush, starts_combat=True."""
        r = resolve_bad_movement_event(3, is_dangerous=True)
        assert r.event_type == "ambush"
        assert r.starts_combat is True
        assert r.extra_damage == 0
        assert r.description == "You were ambushed!"

    def test_nothing(self):
        """Rolls 4-6 → nothing, zero values, empty description."""
        for roll in (4, 5, 6):
            r = resolve_bad_movement_event(roll)
            assert r.event_type == "nothing"
            assert r.extra_damage == 0
            assert r.starts_combat is False
            assert r.description == ""

    def test_ambush_safe_fallback(self):
        """Roll 3 + is_dangerous=False → fallback to trap."""
        r = resolve_bad_movement_event(3, is_dangerous=False, rng=_seq_rng([4]))
        assert r.event_type == "trap"
        assert r.extra_damage == 4
        assert r.starts_combat is False
        assert r.description == "You stepped into a trap."


# ─── Integration tests for _handle_movement_failure ──────

class TestHandleMovementFailureBadEvents:
    """Bad events in _handle_movement_failure integration tests."""

    def test_roll_1_triggers_bad_event(self):
        """Movement roll=1 (fail_bad) → bad event applied (trap)."""
        st = make_state()
        # RNG order (called directly in _handle_movement_failure):
        # [event_roll, damage_roll, bad_roll, extra_roll]
        # event=1(stone), damage=5, bad=1(trap), extra=3
        rng = _seq_rng([1, 5, 1, 3])
        result = _handle_movement_failure(
            "north", "fail_bad", st["hidden"], st["visible"], rng,
        )
        assert isinstance(result, ActionResult)
        # HP = 10 - 5 (stone) - 3 (trap) = 2
        assert st["visible"]["hp"] == 2
        assert st["hidden"]["hp_raw"] == 2
        # Event message should contain direction and micro event
        assert any("north" in ev for ev in result.events)
        # Trap description should be in events
        assert any("trap" in ev.lower() for ev in result.events)

    def test_roll_2_no_bad_event(self):
        """Movement roll=2 (fail) → resolve_bad_movement_event NOT called."""
        st = make_state()
        # Monkeypatch to detect if resolve_bad_movement_event is called
        import burt.loop as loop_mod
        original_func = loop_mod.resolve_bad_movement_event
        called = {"n": 0}

        def mock_bad_event(*args, **kwargs):
            called["n"] += 1
            raise AssertionError(
                "resolve_bad_movement_event should NOT be called for fail (roll=2)"
            )

        loop_mod.resolve_bad_movement_event = mock_bad_event
        try:
            # RNG order (called directly in _handle_movement_failure):
            # [event_roll, damage_roll] — NO bad_roll call for fail
            # event=1(stone), damage=1
            rng = _seq_rng([1, 1])
            result = _handle_movement_failure(
                "north", "fail", st["hidden"], st["visible"], rng,
            )
            assert isinstance(result, ActionResult)
            # HP = 10 - 1 = 9
            assert st["visible"]["hp"] == 9
            assert st["hidden"]["hp_raw"] == 9
            # Monkeypatch should NOT have been called (regression guard)
            assert called["n"] == 0, (
                "resolve_bad_movement_event was called for fail (roll=2)"
            )
        finally:
            loop_mod.resolve_bad_movement_event = original_func

    def test_bad_event_ambush_in_loop_starts_combat(self):
        """Movement roll=1 + bad_roll=3 in dangerous location → combat started."""
        graph = _mini_graph("лес", {"north": "target"})
        st = {
            "visible": {
                "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
                "level": 1,
                "eat": True, "sleep_counter": 5, "date": "1 день",
                "effects": [],
                "location": {"name": "Forest", "exits": ["north"]},
                "inventory": [],
                "wallet": {"gold": 0, "silver": 5, "copper": 0},
                "skills_visible": [],
            },
            "hidden": {
                "current_mode": "exploring",
                "current_node_id": "source",
                "location_graph": graph,
                "combat": None,
                "hp_raw": 10, "mp_raw": 3,
                "spells": {"element": None, "alignment": None},
                "step": 0, "day": 1,
            },
        }
        # RNG order (called directly in _handle_movement_failure):
        # [event_roll, damage_roll, bad_roll, spawn_roll1, spawn_roll2]
        # event=1(stone), damage=1, bad=3(ambush), spawn×2
        rng = _seq_rng([1, 1, 3, 1, 1])
        result = _handle_movement_failure(
            "north", "fail_bad", st["hidden"], st["visible"], rng,
        )
        assert isinstance(result, ActionResult)
        assert st["hidden"]["current_mode"] == "combat"
        assert st["hidden"]["combat"] is not None
        assert any("[БОЙ]" in ev for ev in result.events)

    def test_bad_event_does_not_start_combat_if_burt_dead(self):
        """HP=0 after micro+bad event → game_over=True, combat NOT started."""
        st = make_state()
        # RNG order (called directly in _handle_movement_failure):
        # [event_roll, damage_roll, bad_roll, extra_roll]
        # event=1(stone), damage=6, bad=1(trap), extra=6
        # HP = 10 - 6 - 6 = -1 → cap 0 → game_over=True
        rng = _seq_rng([1, 6, 1, 6])
        result = _handle_movement_failure(
            "north", "fail_bad", st["hidden"], st["visible"], rng,
        )
        assert isinstance(result, ActionResult)
        assert result.game_over is True
        assert st["visible"]["hp"] == 0
        assert st["hidden"]["hp_raw"] == 0
        assert st["hidden"]["current_mode"] == "exploring"
        assert st["hidden"]["combat"] is None

    def test_micro_location_preserved_after_bad_combat(self):
        """After ambush combat, micro_location.active=True, source/target intact."""
        graph = _mini_graph("лес", {"north": "target"})
        st = {
            "visible": {
                "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
                "level": 1,
                "eat": True, "sleep_counter": 5, "date": "1 день",
                "effects": [],
                "location": {"name": "Forest", "exits": ["north"]},
                "inventory": [],
                "wallet": {"gold": 0, "silver": 5, "copper": 0},
                "skills_visible": [],
            },
            "hidden": {
                "current_mode": "exploring",
                "current_node_id": "source",
                "location_graph": graph,
                "combat": None,
                "hp_raw": 10, "mp_raw": 3,
                "spells": {"element": None, "alignment": None},
                "step": 0, "day": 1,
            },
        }
        # RNG order (called directly in _handle_movement_failure):
        # [event_roll, damage_roll, bad_roll, spawn_roll1, spawn_roll2]
        # event=1(stone), damage=1, bad=3(ambush), spawn×2
        rng = _seq_rng([1, 1, 3, 1, 1])
        result = _handle_movement_failure(
            "north", "fail_bad", st["hidden"], st["visible"], rng,
        )
        assert isinstance(result, ActionResult)
        micro = st["hidden"].get("micro_location")
        assert micro is not None
        assert micro["active"] is True
        assert micro["source_node"] == "source"
        assert micro["target_node"] == "target"
        assert micro["direction"] == "north"

    def test_ambush_in_safe_location_falls_back_to_trap(self):
        """Movement roll=1 + bad_roll=3 in safe location → trap fallback, no combat."""
        st = make_state()
        # RNG order (called directly in _handle_movement_failure):
        # [event_roll, damage_roll, bad_roll, extra_roll]
        # event=1(stone), damage=1, bad=3(fallback trap), extra=5
        # HP = 10 - 1 - 5 = 4
        rng = _seq_rng([1, 1, 3, 5])
        result = _handle_movement_failure(
            "north", "fail_bad", st["hidden"], st["visible"], rng,
        )
        assert isinstance(result, ActionResult)
        assert st["hidden"]["current_mode"] == "exploring"
        assert st["hidden"]["combat"] is None
        assert st["visible"]["hp"] == 4
        # Trap description should be in events
        assert any("trap" in ev.lower() for ev in result.events)
        # [БОЙ] should NOT be in events
        assert not any("[БОЙ]" in ev for ev in result.events)