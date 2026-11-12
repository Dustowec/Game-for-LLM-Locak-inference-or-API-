"""Tests for search fix — HANDOFF-9.2.

Covered:
- search increments step exactly once per call (with deterministic rng).
- search uses rng() instead of dice.roll_d6() directly.
- search does not reference hidden["location_types"] (uses forest table).
- search returns stable search_result field.

All docstrings/comments in English. No Cyrillic literals.
"""

import pytest

from burt.loop import Action, execute_action


# ─── Helpers ───────────────────────────────────────────────

def make_state_no_location_types():
    """State without hidden['location_types'] — simulates current state.py."""
    from burt import world
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": "1 day",
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
            # NOTE: no "location_types" key — this is the current state.py shape.
        },
    }


def make_state_with_location_types():
    """State with hidden['location_types'] — should be ignored by search."""
    from burt import world
    st = make_state_no_location_types()
    st["hidden"]["location_types"] = {"start": "river"}
    return st


# ─── TestSearchFix ─────────────────────────────────────────

class TestSearchFix:
    """Verify HANDOFF-9.2 search fixes."""

    def test_search_increments_step_once(self):
        """One search call with rng → step increases by exactly 1."""
        st = make_state_no_location_types()
        st["hidden"]["step"] = 5
        execute_action(Action("search", "Search"), st, rng=lambda: 4)
        assert st["hidden"]["step"] == 6

    def test_search_uses_rng_not_random(self):
        """Deterministic rng produces deterministic search_result."""
        st = make_state_no_location_types()
        r1 = execute_action(Action("search", "Search"), st, rng=lambda: 4)
        r2 = execute_action(Action("search", "Search"), st, rng=lambda: 4)
        assert r1.search_result == r2.search_result

    def test_search_does_not_reference_location_types(self):
        """Search returns stable result without hidden['location_types']."""
        st = make_state_no_location_types()
        assert "location_types" not in st["hidden"]
        result = execute_action(
            Action("search", "Search"), st, rng=lambda: 4,
        )
        assert result.search_result == "partial"  # roll=4 → partial
        assert len(result.events) == 2  # search_result + sensory report

    def test_search_uses_forest_table_regardless_of_location_type(self):
        """Even with location_types present, search uses forest table."""
        st = make_state_with_location_types()
        result = execute_action(
            Action("search", "Search"), st, rng=lambda: 4,
        )
        # roll=4 → "partial" from forest table (same as without location_types)
        assert result.search_result == "partial"
