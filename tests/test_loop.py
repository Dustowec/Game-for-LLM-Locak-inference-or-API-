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
    """Базовое state: exploring, 4 выхода, world-граф старта."""
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
            "inventory": [
                {"name": "bread", "count": 2},
                {"name": "water", "count": 1},
            ],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
        },
        "hidden": {
            "current_mode": mode,
            "current_node_id": "start",
            "location_graph": world.create_start_graph(),
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
        st["visible"]["inventory"] = [{"name": "bread", "count": 1}]
        assert "eat_food" in _keys(build_menu(st["visible"], st))

    def test_drink_water_present_with_water(self):
        st = make_state()
        st["visible"]["inventory"] = [{"name": "water", "count": 1}]
        assert "drink_water" in _keys(build_menu(st["visible"], st))

    def test_no_eat_food_without_bread(self):
        st = make_state()
        st["visible"]["inventory"] = [{"name": "sword", "count": 1}]
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
        assert "block" not in keys
        assert "flee" not in keys

    def test_empty_when_combat_missing(self):
        st = make_state("combat")
        st["hidden"]["combat"] = None
        assert build_menu(st["visible"], st) == []


# ─── parse_choice (базовые) ────────────────────────────────

class TestParseChoice:
    def _two(self):
        return [Action("a", "A"), Action("b", "B")]

    def test_numbered_zero(self):
        assert parse_choice("CHOICE: 0", self._two()).key == "a"

    def test_numbered_one(self):
        assert parse_choice("CHOICE: 1", self._two()).key == "b"

    def test_prefix_match_by_label(self):
        actions = [Action("special", "Secret passage")]
        assert parse_choice(
            "I take the Secret passage now", actions,
        ).key == "special"

    def test_fallback_first_on_unknown(self):
        assert parse_choice("qwerty", self._two()).key == "a"

    def test_empty_menu_returns_osmotret(self):
        assert parse_choice("CHOICE: 0", []).key == "osmotret"

    def test_invalid_number_fallback(self):
        assert parse_choice("CHOICE: 99", self._two()).key == "a"


# ─── parse_choice: синонимы + rfind (П.1) ──────────────────

class TestParseChoiceSynonyms:
    """П.1: text fallback with verb synonyms; last mention wins."""

    def _menu(self):
        return [
            Action("osmotret", "Look around"),
            Action("go_north", "Go north"),
            Action("go_east", "Go east"),
            Action("search", "Search"),
        ]

    def test_walk_north_synonym(self):
        assert parse_choice("I walk north.", self._menu()).key == "go_north"

    def test_step_north_synonym(self):
        assert parse_choice("I step north.", self._menu()).key == "go_north"

    def test_head_north_synonym(self):
        assert parse_choice("I head north.", self._menu()).key == "go_north"

    def test_look_around_synonym(self):
        assert parse_choice("I look around.", self._menu()).key == "osmotret"

    def test_check_surroundings_synonym(self):
        assert parse_choice(
            "I check my surroundings.", self._menu(),
        ).key == "osmotret"

    def test_last_mention_wins(self):
        text = "I look around. Then I walk north."
        assert parse_choice(text, self._menu()).key == "go_north"

    def test_last_mention_wins_reverse(self):
        text = "I walk north. Then I look around."
        assert parse_choice(text, self._menu()).key == "osmotret"

    def test_rummage_for_search(self):
        assert parse_choice("I rummage.", self._menu()).key == "search"

    def test_look_for_is_search_not_osmotret(self):
        assert parse_choice("I look for food.", self._menu()).key == "search"

    def test_eat_synonym(self):
        menu = [
            Action("osmotret", "Look around"),
            Action("eat_food", "Eat food"),
        ]
        assert parse_choice("I eat the bread.", menu).key == "eat_food"

    def test_choice_number_wins_over_text(self):
        # CHOICE: 0 wins even though text mentions walk north.
        text = "I walk north.\nCHOICE: 0"
        assert parse_choice(text, self._menu()).key == "osmotret"

    def test_empty_choice_falls_to_text(self):
        # "CHOICE:" with nothing after -> text fallback.
        text = "CHOICE:\nI walk north."
        assert parse_choice(text, self._menu()).key == "go_north"


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
        result = execute_action(Action("go_north", "Go"), st,
                                rng=lambda: 4)
        assert st["hidden"]["current_node_id"] != "start"
        assert st["hidden"]["step"] == 1
        assert st["visible"]["location"]["name"] == "Road"
        assert isinstance(result, ActionResult)

    def test_go_invalid_direction_returns_error(self):
        st = make_state()
        result = execute_action(Action("go_up", "Go"), st)
        assert any("error" in ev.lower() for ev in result.events)
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
        assert any("error" in ev.lower() for ev in result.events)


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
        assert "error" in r.events[0].lower()


# ─── _resolve_location_name ────────────────────────────────

class TestResolveLocationName:
    def test_known_type_crossroads(self):
        assert _resolve_location_name("crossroads", "start") == "Crossroads"

    def test_known_type_forest(self):
        assert _resolve_location_name("forest", "forest_1") == "Forest"

    def test_unknown_type_falls_back_to_node_id(self):
        assert _resolve_location_name("zxc", "node_42") == "node_42"

    def test_empty_type_falls_back(self):
        assert _resolve_location_name("", "abc") == "abc"


# ─── osmotret repeat punishment (§25.1) ────────────────────

class TestOsmotretPunishment:
    """3rd+ osmotret in a row costs 1 HP (scared behavior)."""

    def test_first_osmotret_normal(self):
        st = make_state()
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 10
        assert not any("branch" in e.lower() for e in r.events)

    def test_second_osmotret_warns(self):
        st = make_state()
        execute_action(Action("osmotret", "Look"), st)
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 10
        assert any("nothing has changed" in e.lower() for e in r.events)

    def test_third_osmotret_damages(self):
        st = make_state()
        execute_action(Action("osmotret", "Look"), st)
        execute_action(Action("osmotret", "Look"), st)
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 9
        assert st["hidden"]["hp_raw"] == 9
        assert any("branch" in e.lower() for e in r.events)

    def test_fourth_osmotret_damages_again(self):
        st = make_state()
        for _ in range(3):
            execute_action(Action("osmotret", "Look"), st)
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 8
        assert any("branch" in e.lower() for e in r.events)

    def test_other_action_resets_counter(self):
        st = make_state()
        execute_action(Action("osmotret", "Look"), st)
        execute_action(Action("osmotret", "Look"), st)
        execute_action(Action("search", "Search"), st, rng=lambda: 3)
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 10
        assert not any("nothing has changed" in e.lower() for e in r.events)

    def test_osmotret_can_kill(self):
        st = make_state()
        st["visible"]["hp"] = 1
        st["hidden"]["hp_raw"] = 1
        execute_action(Action("osmotret", "Look"), st)
        execute_action(Action("osmotret", "Look"), st)
        r = execute_action(Action("osmotret", "Look"), st)
        assert st["visible"]["hp"] == 0
        assert r.game_over is True

    class TestLethalMovement:
        """Проверка, что смертельный урон от микро-события вызывает game_over (даже при обычном fail)."""

    def test_movement_fail_can_kill(self):
        st = make_state()
        st["visible"]["hp"] = 1
        st["hidden"]["hp_raw"] = 1
        
        # rng side_effect:
        # 1. move_roll (2 -> fail)
        # 2. event_roll (6 -> lightning)
        # 3+. damage_roll (6 -> max damage)
        rolls = [2, 6, 6, 6, 6, 6, 6]
        def rng():
            return rolls.pop(0) if rolls else 6

        result = execute_action(Action("go_north", "Go"), st, rng=rng)
        
        assert st["visible"]["hp"] == 0
        assert result.game_over is True, "Должен быть game_over, если HP упало до 0 от молнии"