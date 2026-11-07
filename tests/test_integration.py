"""Integration tests for loop.py + llm_client.py + sensory.

Full cycle: sensory report -> LLM response (mocked) -> parse_choice -> execute_action -> state mutation.
"""
import pytest

from burt.loop import Action, ActionResult, build_menu, parse_choice, execute_action, should_sleep, error_result
from burt import sensory
from burt.prompts import BURT_SYSTEM_PROMPT
from burt.llm_client import extract_answer, extract_finish_reason
from burt.combat import start_combat
from burt.bestiary import ENEMIES


def make_state(mode="exploring"):
    from burt import world
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": "1 day",
            "effects": [],
            "location": {"name": "Crossroads", "exits": ["north", "east", "south", "west"]},
            "inventory": [{"name": "хлеб", "count": 2}, {"name": "вода", "count": 1}],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
        },
        "hidden": {
            "current_mode": mode, "current_node_id": "start",
            "location_graph": world.create_start_graph(),
            "room_tonight": False, "day": 1, "step": 0, "diary_entries": [],
        },
    }


class TestSensoryReportGeneration:
    def test_report_contains_hp(self):
        st = make_state()
        report = sensory.format_sensory_report(st["visible"])
        assert "HP" in report

    def test_report_contains_location(self):
        st = make_state()
        report = sensory.format_sensory_report(st["visible"])
        assert "[МЕСТО]" in report

    def test_report_contains_inventory(self):
        st = make_state()
        report = sensory.format_sensory_report(st["visible"])
        assert "[РУКИ]" in report

    def test_report_is_non_empty_string(self):
        st = make_state()
        report = sensory.format_sensory_report(st["visible"])
        assert isinstance(report, str)
        assert len(report) > 10


class TestSystemPromptConstruction:
    def test_prompt_mentions_burt(self):
        assert "Бурт" in BURT_SYSTEM_PROMPT

    def test_prompt_has_format_instructions(self):
        assert "ВЫБОР" in BURT_SYSTEM_PROMPT

    def test_prompt_forbids_ai_behavior(self):
        assert "ИЙ" in BURT_SYSTEM_PROMPT or "ассистент" in BURT_SYSTEM_PROMPT.lower()


class TestFullCycleExploration:
    def test_cycle_osmotret(self):
        st = make_state()
        menu = build_menu(st["visible"], st)
        keys = [a.key for a in menu]
        assert "osmotret" in keys
        llm_response = "I look around.\nункт 1\n"
        chosen = parse_choice(llm_response, menu)
        assert chosen.key == "osmotret"
        result = execute_action(chosen, st)
        assert "осмотр" in result.events
        assert st["hidden"]["step"] == 1

    def test_cycle_go_north(self):
        st = make_state()
        menu = build_menu(st["visible"], st)
        keys = [a.key for a in menu]
        assert "go_north" in keys
        llm_response = "Going north.\nункт 2\n"
        chosen = parse_choice(llm_response, menu)
        assert chosen.key == "go_north"
        result = execute_action(chosen, st, rng=lambda: 4)
        assert len(result.events) > 0
        assert st["hidden"]["step"] == 1

# ---------------------------------------------------------------------
# Помощники для боевых тестов (новая модель: hidden["combat"])
# ---------------------------------------------------------------------

def _fleeable_enemy_key():
    """Первый враг из bestiary без тега no_flee."""
    for k, e in ENEMIES.items():
        if not (e.tags and "no_flee" in e.tags):
            return k
    raise RuntimeError("no fleeable enemy in bestiary")


def _put_combat(st, enemy_keys, initiative="burt"):
    """Положить бой в hidden["combat"] через start_combat."""
    cs = start_combat(enemy_keys, initiative)
    st["hidden"]["combat"] = cs.to_dict()
    st["hidden"]["current_mode"] = "combat"
    return cs


class TestFullCycleCombat:
    def test_combat_menu_has_actions(self):
        st = make_state("combat")
        _put_combat(st, [_fleeable_enemy_key()])
        menu = build_menu(st["visible"], st)
        keys = [a.key for a in menu]
        assert any(k.startswith("attack_") for k in keys)
        assert "block" in keys
        assert "flee" in keys

    def test_cycle_attack_reduces_enemy_hp(self):
        st = make_state("combat")
        cs = _put_combat(st, [_fleeable_enemy_key()])
        hp_before = cs.enemies[0].hp
        menu = build_menu(st["visible"], st)
        attack_action = next(a for a in menu if a.key.startswith("attack_"))
        # rng = 5 -> попадание с максимальным уроном
        result = execute_action(attack_action, st, rng=lambda: 5)
        assert isinstance(result, ActionResult)
        new_hp = st["hidden"]["combat"]["enemies"][0]["hp"]
        assert new_hp < hp_before

    def test_cycle_attack_kills_when_hp_low(self):
        st = make_state("combat")
        _put_combat(st, [_fleeable_enemy_key()])
        # Обнулим HP врага вручную — удар на 5 гарантированно добьёт.
        st["hidden"]["combat"]["enemies"][0]["hp"] = 1
        menu = build_menu(st["visible"], st)
        attack_action = next(a for a in menu if a.key.startswith("attack_"))
        result = execute_action(attack_action, st, rng=lambda: 5)
        assert st["hidden"]["combat"] is None
        assert st["hidden"]["current_mode"] == "exploring"
        # При завершении боя [БОЙ] в events не подмешивается.
        assert not any("[БОЙ]" in ev for ev in result.events)

    def test_cycle_block_keeps_combat(self):
        st = make_state("combat")
        _put_combat(st, [_fleeable_enemy_key()])
        block_action = Action(key="block", label="Block")
        result = execute_action(block_action, st, rng=lambda: 5)
        assert any("защит" in e for e in result.events)
        assert st["hidden"]["current_mode"] == "combat"
        assert st["hidden"]["combat"] is not None

    def test_cycle_flee_success_ends_combat(self):
        st = make_state("combat")
        _put_combat(st, [_fleeable_enemy_key()])
        flee_action = Action(key="flee", label="Flee")
        result = execute_action(flee_action, st, rng=lambda: 5)
        assert any("убежал" in e for e in result.events)
        assert st["hidden"]["current_mode"] == "exploring"
        assert st["hidden"]["combat"] is None

class TestParseChoiceEdgeCases:
    def test_parse_numbered_zero(self):
        actions = [Action("a", "A"), Action("b", "B")]
        result = parse_choice("Ы: 0", actions)
        assert result.key == "a"

    def test_parse_numbered_one(self):
        actions = [Action("a", "A"), Action("b", "B")]
        result = parse_choice("Ы: 1", actions)
        assert result.key == "b"

    def test_parse_prefix_match(self):
        actions = [Action("go_north", "насер")]
        result = parse_choice("насер пожалуйста", actions)
        assert result.key == "go_north"

    def test_parse_fallback_first(self):
        actions = [Action("a", "A"), Action("b", "B")]
        result = parse_choice("Unknown input", actions)
        assert result.key == "a"

    def test_parse_empty_menu_returns_osmotret(self):
        result = parse_choice("Ы: 0", [])
        assert result.key == "osmotret"

    def test_parse_invalid_number_fallback(self):
        actions = [Action("a", "A")]
        result = parse_choice("Ы: 99", actions)
        assert result.key == "a"


class TestShouldSleepIntegration:
    def test_sleep_at_threshold(self):
        st = make_state()
        st["visible"]["sleep_counter"] = 20
        assert should_sleep(st["visible"], st) is True

    def test_no_sleep_when_fresh(self):
        st = make_state()
        st["visible"]["sleep_counter"] = 5
        assert should_sleep(st["visible"], st) is False

    def test_sleep_at_critical_hp(self):
        st = make_state()
        st["visible"]["hp"] = 1
        st["visible"]["hp_max"] = 10
        assert should_sleep(st["visible"], st) is True

    def test_no_sleep_healthy(self):
        st = make_state()
        st["visible"]["hp"] = 8
        st["visible"]["hp_max"] = 10
        assert should_sleep(st["visible"], st) is False


class TestLLMClientIntegration:
    def test_extract_answer_from_valid_response(self):
        raw = {
            "choices": [{
                "message": {"content": "Тьма вокруг. Я иду на насер."},
                "finish_reason": "stop"
            }]
        }
        answer = extract_answer(raw)
        assert answer == "Тьма вокруг. Я иду на насер."

    def test_extract_answer_empty_content(self):
        raw = {"choices": [{"message": {"content": ""}}]}
        assert extract_answer(raw) == ""

    def test_extract_answer_no_choices(self):
        raw = {}
        assert extract_answer(raw) == ""

    def test_extract_finish_reason_stop(self):
        raw = {"choices": [{"finish_reason": "stop"}]}
        assert extract_finish_reason(raw) == "stop"

    def test_extract_finish_reason_none(self):
        raw = {}
        assert extract_finish_reason(raw) is None


class TestStateMutationConsistency:
    def test_step_increments_on_action(self):
        st = make_state()
        initial_step = st["hidden"]["step"]
        menu = build_menu(st["visible"], st)
        action = menu[0]
        execute_action(action, st)
        assert st["hidden"]["step"] == initial_step + 1

    def test_location_changes_after_go(self):
        st = make_state()
        menu = build_menu(st["visible"], st)
        go_action = None
        for a in menu:
            if a.key == "go_north":
                go_action = a
                break
        assert go_action is not None
        execute_action(go_action, st, rng=lambda: 4)
        new_name = st["visible"]["location"]["name"]
        assert new_name == "Road"  # world preset: north = дорога

    def test_hp_restored_after_sleep(self):
        st = make_state()
        st["visible"]["hp"] = 3
        st["visible"]["sleep_counter"] = 19
        menu = build_menu(st["visible"], st)
        sleep_action = None
        for a in menu:
            if a.key == "sleep":
                sleep_action = a
                break
        assert sleep_action is not None
        execute_action(sleep_action, st)
        assert st["visible"]["hp"] == st["visible"]["hp_max"]
        assert st["visible"]["mp"] == st["visible"]["mp_max"]
        assert st["visible"]["effects"] == []
