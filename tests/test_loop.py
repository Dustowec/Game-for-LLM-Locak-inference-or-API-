"""Тесты loop.py — §26, синхронное ядро игрового цикла.

Покрывают build_menu, parse_choice, execute_action, should_sleep,
error_result, _resolve_location_name.

Боевой стык с combat.resolve_round — отдельно в test_loop_combat.py,
здесь только меню боя (что visible -> Action[]).

Восстановлен после случайной перезаписи (HANDOFF-8).
"""

import pytest

from burt.loop import (
    Action, ActionResult,
    build_menu, parse_choice, execute_action,
    should_sleep, error_result, _resolve_location_name,
    DIRECTIONS, SLEEP_THRESHOLD, CRITICAL_HP_RATIO,
)
from burt.combat import start_combat
from burt.bestiary import ENEMIES


# ─── Общий помощник ────────────────────────────────────────

def make_state(mode="exploring"):
    """Базовое state: exploring, 4 выхода, стартовая локация."""
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": "1 день",
            "effects": [],
            "location": {
                "name": "Crossroads",
                "exits": ["north", "east", "south", "west"],
            },
            "inventory": [
                {"name": "хлеб", "count": 2},
                {"name": "вода", "count": 1},
            ],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
            "state": "exploring",
        },
        "hidden": {
            "current_mode": mode,
            "current_node_id": "start",
            "location_graph": {
                "start": {"north": "forest_1", "east": None,
                          "south": None, "west": None},
                "forest_1": {"north": None, "east": None,
                             "south": "start", "west": None},
            },
            "location_types": {"start": "старт", "forest_1": "лес"},
            "hp_raw": 10, "mp_raw": 3,
            "spells": {"element": None, "alignment": None},
            "step": 0, "day": 1,
        },
    }


def _keys(actions):
    return [a.key for a in actions]


def _combat_key():
    """Любой враг из bestiary."""
    return next(iter(ENEMIES))


# ─── build_menu: exploring ─────────────────────────────────

class TestBuildMenuExploring:
    def test_has_osmotret(self):
        st = make_state()
        assert "osmotret" in _keys(build_menu(st["visible"], st))

    def test_has_go_for_each_exit(self):
        st = make_state()
        keys = _keys(build_menu(st["visible"], st))
        for d in st["visible"]["location"]["exits"]:
            assert f"go_{d}" in keys

    def test_no_go_for_direction_not_in_exits(self):
        st = make_state()
        st["visible"]["location"]["exits"] = ["north"]
        keys = _keys(build_menu(st["visible"], st))
        assert "go_north" in keys
        assert "go_east" not in keys
        assert "go_south" not in keys
        assert "go_west" not in keys

    def test_has_search(self):
        st = make_state()
        assert "search" in _keys(build_menu(st["visible"], st))

    def test_sleep_absent_at_fresh_counter(self):
        st = make_state()
        st["visible"]["sleep_counter"] = 5
        assert "sleep" not in _keys(build_menu(st["visible"], st))

    def test_sleep_present_at_sc_19(self):
        st = make_state()
        st["visible"]["sleep_counter"] = 19
        assert "sleep" in _keys(build_menu(st["visible"], st))

    def test_sleep_present_at_critical_hp(self):
        st = make_state()
        st["visible"]["hp"] = 2
        st["visible"]["hp_max"] = 10
        assert "sleep" in _keys(build_menu(st["visible"], st))

    def test_eat_food_present_with_bread(self):
        st = make_state()
        st["visible"]["inventory"] = [{"name": "хлеб", "count": 1}]
        assert "eat_food" in _keys(build_menu(st["visible"], st))

    def test_drink_water_present_with_water(self):
        st = make_state()
        st["visible"]["inventory"] = [{"name": "вода", "count": 1}]
        assert "drink_water" in _keys(build_menu(st["visible"], st))

    def test_no_eat_food_without_bread(self):
        st = make_state()
        st["visible"]["inventory"] = [{"name": "меч", "count": 1}]
        keys = _keys(build_menu(st["visible"], st))
        assert "eat_food" not in keys
        assert "drink_water" not in keys


# ─── build_menu: dialog ────────────────────────────────────

class TestBuildMenuDialog:
    def test_only_exit_dialog(self):
        st = make_state("dialog")
        actions = build_menu(st["visible"], st)
        assert _keys(actions) == ["exit_dialog"]


# ─── build_menu: combat ────────────────────────────────────

class TestBuildMenuCombat:
    def test_attack_line_per_live_enemy(self):
        st = make_state("combat")
        cs = start_combat([_combat_key()], "burt")
        st["hidden"]["combat"] = cs.to_dict()
        keys = _keys(build_menu(st["visible"], st))
        assert f"attack_{cs.enemies[0].id}" in keys

    def test_block_and_flee_present(self):
        st = make_state("combat")
        cs = start_combat([_combat_key()], "burt")
        st["hidden"]["combat"] = cs.to_dict()
        keys = _keys(build_menu(st["visible"], st))
        assert "block" in keys
        assert "flee" in keys

    def test_no_attack_for_dead_enemy(self):
        st = make_state("combat")
        cs = start_combat([_combat_key()], "burt")
        cs.enemies[0].alive = False
        st["hidden"]["combat"] = cs.to_dict()
        keys = _keys(build_menu(st["visible"], st))
        assert f"attack_{cs.enemies[0].id}" not in keys
        # Все мертвы -> нет ни block, ни flee
        assert "block" not in keys
        assert "flee" not in keys

    def test_empty_when_combat_missing(self):
        st = make_state("combat")
        st["hidden"]["combat"] = None
        assert build_menu(st["visible"], st) == []


# ─── parse_choice ──────────────────────────────────────────

class TestParseChoice:
    def _two(self):
        return [Action("a", "A"), Action("b", "B")]

    def test_numbered_zero(self):
        assert parse_choice("Ы: 0", self._two()).key == "a"

    def test_numbered_one(self):
        assert parse_choice("Ы: 1", self._two()).key == "b"

    def test_prefix_match_by_label(self):
        actions = [Action("go_north", "на сервер")]
        assert parse_choice("иду на сервер", actions).key == "go_north"

    def test_fallback_first_on_unknown(self):
        assert parse_choice("qwerty", self._two()).key == "a"

    def test_empty_menu_returns_osmotret(self):
        assert parse_choice("Ы: 0", []).key == "osmotret"

    def test_invalid_number_fallback(self):
        assert parse_choice("Ы: 99", self._two()).key == "a"


# ─── execute_action: мирные действия ───────────────────────

class TestExecuteActionExploring:
    def test_osmotret_returns_report_and_increments_step(self):
        st = make_state()
        result = execute_action(Action("osmotret", "Look"), st)
        assert isinstance(result, ActionResult)
        assert st["hidden"]["step"] == 1
        assert len(result.events) >= 1

    def test_go_north_moves_and_increments_step(self):
        st = make_state()
        result = execute_action(Action("go_north", "Go"), st)
        assert st["hidden"]["current_node_id"] == "forest_1"
        assert st["hidden"]["step"] == 1
        assert st["visible"]["location"]["name"] == "Forest"
        assert isinstance(result, ActionResult)

    def test_go_invalid_direction_returns_error(self):
        st = make_state()
        result = execute_action(Action("go_up", "Go"), st)
        assert any("ошибка" in ev.lower() for ev in result.events)
        assert st["hidden"]["step"] == 0

    def test_sleep_restores_hp_and_mp(self):
        st = make_state()
        st["visible"]["hp"] = 3
        st["visible"]["mp"] = 1
        st["hidden"]["hp_raw"] = 3
        st["hidden"]["mp_raw"] = 1
        result = execute_action(Action("sleep", "Sleep"), st)
        assert st["visible"]["hp"] == st["visible"]["hp_max"]
        assert st["visible"]["mp"] == st["visible"]["mp_max"]
        assert st["hidden"]["hp_raw"] == st["visible"]["hp_max"]
        assert st["hidden"]["mp_raw"] == st["visible"]["mp_max"]
        assert st["hidden"]["day"] == 2
        assert st["hidden"]["step"] == 0
        assert isinstance(result, ActionResult)

    def test_sleep_resets_effects(self):
        st = make_state()
        st["visible"]["effects"] = ["blessed", "cursed"]
        execute_action(Action("sleep", "Sleep"), st)
        assert st["visible"]["effects"] == []

    def test_unknown_action_returns_error(self):
        st = make_state()
        result = execute_action(Action("teleport", "TP"), st)
        assert any("ошибка" in ev.lower() for ev in result.events)


# ─── should_sleep ──────────────────────────────────────────

class TestShouldSleep:
    def test_true_at_sleep_threshold(self):
        st = make_state()
        st["visible"]["sleep_counter"] = SLEEP_THRESHOLD
        assert should_sleep(st["visible"], st) is True

    def test_false_when_fresh(self):
        st = make_state()
        st["visible"]["sleep_counter"] = 5
        assert should_sleep(st["visible"], st) is False

    def test_true_at_critical_hp(self):
        st = make_state()
        st["visible"]["hp"] = 1
        st["visible"]["hp_max"] = 10
        assert should_sleep(st["visible"], st) is True

    def test_false_when_healthy(self):
        st = make_state()
        st["visible"]["hp"] = 8
        st["visible"]["hp_max"] = 10
        assert should_sleep(st["visible"], st) is False


# ─── error_result ──────────────────────────────────────────

class TestErrorResult:
    def test_returns_action_result(self):
        r = error_result("boom")
        assert isinstance(r, ActionResult)

    def test_events_contain_message_with_prefix(self):
        r = error_result("boom")
        assert len(r.events) == 1
        assert "boom" in r.events[0]
        assert "ошибка" in r.events[0].lower()


# ─── _resolve_location_name ────────────────────────────────

class TestResolveLocationName:
    def test_known_type_старт(self):
        assert _resolve_location_name("старт", "start") == "Crossroads"

    def test_known_type_лес(self):
        assert _resolve_location_name("лес", "forest_1") == "Forest"

    def test_unknown_type_falls_back_to_node_id(self):
        assert _resolve_location_name("zxc", "node_42") == "node_42"

    def test_empty_type_falls_back(self):
        assert _resolve_location_name("", "abc") == "abc"