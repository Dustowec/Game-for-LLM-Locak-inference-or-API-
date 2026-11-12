"""Tests for positive movement events (HANDOFF-9.3).

Covered:
- dice.resolve_movement_event: roll 5 -> loot, roll 6 -> blessing, 1-4 -> nothing.
- loop.py go_ handler: positive event applied after successful movement,
  only when on-entry did NOT start combat.
- Blessing caps hp/mp at max.
- Loot adds gold to wallet.

All docstrings/comments in English. No Cyrillic literals.
"""

import pytest

from burt.loop import (
    Action, ActionResult, execute_action,
)
from burt.dice import resolve_movement_event, MovementEventResult
from burt import world


def make_state():
    """Base state: exploring, world-graph start."""
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": "1 day",
            "effects": [],
            "location": {"name": "Crossroads", "exits": ["north", "east", "south", "west"]},
            "inventory": [],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
        },
        "hidden": {
            "current_mode": "exploring", "current_node_id": "start",
            "location_graph": world.create_start_graph(), "combat": None,
            "hp_raw": 10, "mp_raw": 3,
            "spells": {"element": None, "alignment": None},
            "step": 0, "day": 1,
        },
    }


def _seq_rng(values):
    """rng returning values in order; stays on the last one."""
    values = list(values)
    if not values:
        raise ValueError("_seq_rng needs at least one value")
    state = {"i": 0}
    def _rng():
        i = min(state["i"], len(values) - 1)
        state["i"] += 1
        return values[i]
    return _rng


class TestMovementEventsIntegration:
    """Positive events in the go_ handler of loop.py."""

    def test_roll_5_produces_loot(self):
        """Movement roll=5 -> gold added to wallet, event in results."""
        st = make_state()
        # north->road(safe). rng: [move=5, ec=4, ed=4, et=4, es=4, gold=5]
        rng = _seq_rng([5, 4, 4, 4, 4, 5])
        result = execute_action(Action("go_north", "Go"), st, rng=rng)
        assert isinstance(result, ActionResult)
        assert st["visible"]["wallet"]["gold"] == 5
        assert any("You found some gold." in ev for ev in result.events)

    def test_roll_6_produces_blessing(self):
        """Movement roll=6 -> hp/mp restored (capped), event in results."""
        st = make_state()
        # north->road(safe). rng: [move=6, ec=4, ed=4, et=4, es=4, hr=2, mr=1]
        rng = _seq_rng([6, 4, 4, 4, 4, 2, 1])
        result = execute_action(Action("go_north", "Go"), st, rng=rng)
        assert isinstance(result, ActionResult)
        assert st["visible"]["hp"] == 10
        assert st["hidden"]["hp_raw"] == 10
        assert st["visible"]["mp"] == 3
        assert st["hidden"]["mp_raw"] == 3
        assert any("A blessing restores your vitality." in ev for ev in result.events)

    def test_roll_3_or_4_no_positive_event(self):
        """Rolls 3-4: normal movement, no positive event."""
        st = make_state()
        # north->road(safe). rng: [move=3, ec=4, ed=4, et=4, es=4]
        rng = _seq_rng([3, 4, 4, 4, 4])
        result = execute_action(Action("go_north", "Go"), st, rng=rng)
        assert isinstance(result, ActionResult)
        assert st["visible"]["wallet"]["gold"] == 0
        assert st["visible"]["hp"] == 10
        assert st["visible"]["mp"] == 3
        assert not any("gold" in ev.lower() for ev in result.events)
        assert not any("blessing" in ev.lower() for ev in result.events)

    def test_roll_5_does_not_apply_if_combat_started(self):
        """On-entry initiated combat -> loot NOT applied (order matters)."""
        st = make_state()
        # south->forest(dangerous). rng: [move=5, ec=4, ed=4, et=4, es=4, enc=1]
        rng = _seq_rng([5, 4, 4, 4, 4, 1])
        result = execute_action(Action("go_south", "Go"), st, rng=rng)
        assert st["hidden"]["current_mode"] == "combat"
        assert st["hidden"]["combat"] is not None
        assert st["visible"]["wallet"]["gold"] == 0
        assert any("[COMBAT]" in ev for ev in result.events)
        assert not any("You found some gold." in ev for ev in result.events)

class TestResolveMovementEvent:
    """Unit tests for dice.resolve_movement_event()."""

    def test_roll_5_loot(self):
        r = resolve_movement_event(5, rng=_seq_rng([4]))
        assert r.event_type == "loot"
        assert r.gold == 4
        assert r.hp_restore == 0
        assert r.mp_restore == 0
        assert r.description == "You found some gold."

    def test_roll_6_blessing_caps(self):
        """Blessing restore values capped by hp_max / mp_max."""
        r = resolve_movement_event(6, rng=_seq_rng([5, 4]), hp_max=3, mp_max=1)
        assert r.event_type == "blessing"
        assert r.hp_restore == 3  # min(5, 3)
        assert r.mp_restore == 1  # min(4, 1)

    def test_roll_6_blessing_normal(self):
        """Blessing with generous caps - no capping needed."""
        r = resolve_movement_event(6, rng=_seq_rng([2, 1]), hp_max=10, mp_max=3)
        assert r.event_type == "blessing"
        assert r.hp_restore == 2
        assert r.mp_restore == 1

    def test_roll_other_nothing(self):
        """Rolls 1-4 -> nothing, zero restores."""
        for roll in (1, 2, 3, 4):
            r = resolve_movement_event(roll)
            assert r.event_type == "nothing"
            assert r.gold == 0
            assert r.hp_restore == 0
            assert r.mp_restore == 0
            assert r.description == ""

    def test_rejects_invalid_roll(self):
        with pytest.raises(ValueError):
            resolve_movement_event(0)
        with pytest.raises(ValueError):
            resolve_movement_event(7)

    def test_default_rng_used_when_none(self):
        """When rng=None, defaults to roll_d6 (just checks no crash)."""
        r = resolve_movement_event(5)
        assert r.event_type == "loot"
        assert 1 <= r.gold <= 6
