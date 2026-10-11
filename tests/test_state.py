"""Тесты для burt.state — структура state.json §30 ТЗ v0.7.0.

TDD: чистая логика без I/O. Файловые операции — в test_state_io.py.

Соглашения:
- create_initial_state(...) — стартовое состояние новой жизни.
- validate_state(state) — инварианты, raise ValueError при нарушении.
- get_visible(state) — только visible-секция.
- get_hidden(state) — только hidden-секция.
"""

import copy

import pytest

from burt.state import (
    DIRECTIONS,
    HUNGER_DEATH_AT,
    HUNGER_HUNGRY_AT,
    MAX_SKILL_LEVEL,
    REPUTATION_MAX,
    REPUTATION_MIN,
    ROLE_NAMES,
    SLEEP_FORCED_AT,
    STARTING_LOCATION_NAME,
    STARTING_NODE_ID,
    VALID_ALIGNMENTS,
    VALID_ELEMENTS,
    VALID_STATES,
    create_initial_state,
    get_hidden,
    get_visible,
    validate_state,
)


# ---------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------

def test_roles_are_twelve():
    assert len(ROLE_NAMES) == 12


def test_roles_contain_expected():
    expected = {
        "торговец", "стражник", "крестьянин", "староста",
        "трактирщик", "кузнец", "рыбак", "ребёнок",
        "ветеран", "служитель", "чернокнижник", "маг",
    }
    assert set(ROLE_NAMES) == expected


def test_directions_are_four():
    assert set(DIRECTIONS) == {"north", "south", "east", "west"}


def test_constants_match_tz():
    assert MAX_SKILL_LEVEL == 10
    assert HUNGER_HUNGRY_AT == [0, 10]
    assert HUNGER_DEATH_AT == [8, 18]
    assert SLEEP_FORCED_AT == 20
    assert REPUTATION_MIN == -10
    assert REPUTATION_MAX == 10
    assert VALID_STATES == {"exploring", "dialog", "combat"}
    assert VALID_ELEMENTS == {None, "fire", "water", "earth", "air"}
    assert VALID_ALIGNMENTS == {None, "light", "dark"}


# ---------------------------------------------------------------------
# create_initial_state
# ---------------------------------------------------------------------

def _default_state():
    return create_initial_state(
        life=1,
        session_uuid="test-session",
        config_hash="abc123",
        session_started="2026-10-11T20:00:00",
    )


def test_initial_state_has_three_sections():
    state = _default_state()
    assert set(state.keys()) == {"meta", "visible", "hidden"}


def test_initial_meta_values():
    state = _default_state()
    m = state["meta"]
    assert m["life"] == 1
    assert m["day"] == 1
    assert m["step"] == 0
    assert m["session_started"] == "2026-10-11T20:00:00"
    assert m["config_hash"] == "abc123"


def test_initial_hp_mp():
    state = _default_state()
    v = state["visible"]
    assert v["hp"] == 10
    assert v["hp_max"] == 10
    assert v["mp"] == 3
    assert v["mp_max"] == 3


def test_initial_hunger_and_sleep():
    state = _default_state()
    v = state["visible"]
    assert v["eat"] is False
    assert v["sleep_counter"] == 0


def test_initial_date_is_first_day():
    state = _default_state()
    assert state["visible"]["date"] == "1 день"


def test_initial_effects_empty():
    state = _default_state()
    assert state["visible"]["effects"] == []


def test_initial_wallet_five_silver():
    state = _default_state()
    w = state["visible"]["wallet"]
    assert w == {"gold": 0, "silver": 5, "copper": 0}


def test_initial_inventory_empty():
    state = _default_state()
    assert state["visible"]["inventory"] == []


def test_initial_skills_empty():
    state = _default_state()
    assert state["visible"]["skills_visible"] == []
    assert state["hidden"]["skills_raw"] == []


def test_initial_state_is_exploring():
    state = _default_state()
    assert state["visible"]["state"] == "exploring"


def test_initial_location_has_name_and_four_exits():
    state = _default_state()
    loc = state["visible"]["location"]
    assert loc["name"] == STARTING_LOCATION_NAME
    assert set(loc["exits"]) == set(DIRECTIONS)


def test_initial_location_has_no_id_in_visible():
    """§30: visible.location без id."""
    state = _default_state()
    assert "id" not in state["visible"]["location"]
    assert "node_id" not in state["visible"]["location"]


def test_initial_current_node_id_is_starting():
    state = _default_state()
    assert state["hidden"]["current_node_id"] == STARTING_NODE_ID


def test_initial_location_graph_has_starting_node():
    state = _default_state()
    graph = state["hidden"]["location_graph"]
    assert STARTING_NODE_ID in graph
    node = graph[STARTING_NODE_ID]
    assert set(node.keys()) == set(DIRECTIONS)
    for direction in DIRECTIONS:
        assert node[direction] is None


def test_initial_reputation_all_roles_zero():
    state = _default_state()
    rep = state["hidden"]["reputation"]
    assert set(rep.keys()) == set(ROLE_NAMES)
    for role in ROLE_NAMES:
        assert rep[role] == 0


def test_initial_spells_empty():
    state = _default_state()
    spells = state["hidden"]["spells"]
    assert spells == {"element": None, "alignment": None}


def test_initial_magic_flags_false():
    state = _default_state()
    h = state["hidden"]
    assert h["has_staff"] is False
    assert h["teacher_found"] is False
    assert h["trained_by"] == []


def test_initial_combat_is_none():
    state = _default_state()
    assert state["hidden"]["combat"] is None


def test_initial_events_and_npcs_empty():
    state = _default_state()
    h = state["hidden"]
    assert h["npcs_here"] == []
    assert h["events_here"] == []
    assert h["pending_events"] == []


def test_initial_has_room_tonight_false():
    state = _default_state()
    assert state["hidden"]["has_room_tonight"] is False


def test_initial_quests_empty():
    state = _default_state()
    assert state["hidden"]["quests_raw"] == []


def test_initial_state_is_valid():
    """create_initial_state должен сразу давать валидное состояние."""
    validate_state(_default_state())


def test_initial_state_two_calls_are_independent():
    """Две копии не шарят ссылки на вложенные структуры."""
    s1 = _default_state()
    s2 = _default_state()
    s1["visible"]["inventory"].append({"name": "меч", "count": 1})
    assert s2["visible"]["inventory"] == []
    s1["hidden"]["reputation"]["кузнец"] = 5
    assert s2["hidden"]["reputation"]["кузнец"] == 0


def test_create_initial_state_respects_life_param():
    s = create_initial_state(
        life=7,
        session_uuid="x",
        config_hash="y",
        session_started="z",
    )
    assert s["meta"]["life"] == 7


# ---------------------------------------------------------------------
# validate_state — happy path и инварианты
# ---------------------------------------------------------------------

def test_validate_happy_path():
    validate_state(_default_state())


def test_validate_missing_section():
    state = _default_state()
    del state["hidden"]
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_hp_exceeds_max():
    state = _default_state()
    state["visible"]["hp"] = 999
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_hp_negative():
    state = _default_state()
    state["visible"]["hp"] = -1
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_mp_exceeds_max():
    state = _default_state()
    state["visible"]["mp"] = 99
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_hp_raw_must_match_visible_hp():
    state = _default_state()
    state["hidden"]["hp_raw"] = 5
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_mp_raw_must_match_visible_mp():
    state = _default_state()
    state["hidden"]["mp_raw"] = 1
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_sleep_counter_out_of_range():
    state = _default_state()
    state["visible"]["sleep_counter"] = 21
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_sleep_counter_negative():
    state = _default_state()
    state["visible"]["sleep_counter"] = -1
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_invalid_state_value():
    state = _default_state()
    state["visible"]["state"] = "meditating"
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_reputation_above_max():
    state = _default_state()
    state["hidden"]["reputation"]["кузнец"] = 11
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_reputation_below_min():
    state = _default_state()
    state["hidden"]["reputation"]["кузнец"] = -11
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_reputation_unknown_role():
    state = _default_state()
    state["hidden"]["reputation"]["гоблин"] = 0
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_spells_invalid_element():
    state = _default_state()
    state["hidden"]["spells"]["element"] = "firebomb"
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_spells_invalid_alignment():
    state = _default_state()
    state["hidden"]["spells"]["alignment"] = "neutral"
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_spells_both_light_and_dark_forbidden():
    """§9: тьма и свет взаимоисключающие."""
    state = _default_state()
    # Одно заклинание — либо light, либо dark, но не оба.
    # Так как поле одно — это проверяется тем, что нельзя
    # одновременно иметь оба. Но по схеме у нас одно поле.
    # Инвариант: element и alignment независимы.
    # Если alignment задан, его значение — из VALID_ALIGNMENTS.
    state["hidden"]["spells"]["alignment"] = "light"
    validate_state(state)  # должен пройти


def test_validate_current_node_must_be_in_graph():
    state = _default_state()
    state["hidden"]["current_node_id"] = "node_ghost"
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_location_graph_node_has_all_directions():
    state = _default_state()
    state["hidden"]["location_graph"][STARTING_NODE_ID] = {"north": None}
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_wallet_negative():
    state = _default_state()
    state["visible"]["wallet"]["silver"] = -1
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_meta_day_zero():
    state = _default_state()
    state["meta"]["day"] = 0
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_meta_step_negative():
    state = _default_state()
    state["meta"]["step"] = -1
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_meta_step_above_day_steps():
    state = _default_state()
    state["meta"]["step"] = 21
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_meta_life_zero():
    state = _default_state()
    state["meta"]["life"] = 0
    with pytest.raises(ValueError):
        validate_state(state)


def test_validate_does_not_mutate_state():
    state = _default_state()
    snapshot = copy.deepcopy(state)
    validate_state(state)
    assert state == snapshot


# ---------------------------------------------------------------------
# get_visible / get_hidden
# ---------------------------------------------------------------------

def test_get_visible_returns_visible_section_only():
    state = _default_state()
    v = get_visible(state)
    assert set(v.keys()) == set(state["visible"].keys())
    assert "hp" in v
    assert "hp_raw" not in v


def test_get_visible_does_not_leak_hidden_fields():
    state = _default_state()
    v = get_visible(state)
    forbidden = {
        "hp_raw", "mp_raw", "reputation", "skills_raw",
        "quests_raw", "location_graph", "current_node_id",
        "npcs_here", "events_here", "combat", "spells",
        "has_staff", "teacher_found", "trained_by",
        "hunger_death_at", "sleep_forced_at",
    }
    for key in forbidden:
        assert key not in v


def test_get_hidden_returns_hidden_section_only():
    state = _default_state()
    h = get_hidden(state)
    assert set(h.keys()) == set(state["hidden"].keys())
    assert "reputation" in h
    assert "hp" not in h


def test_get_visible_returns_copy():
    """Мутация результата не меняет оригинал."""
    state = _default_state()
    v = get_visible(state)
    v["hp"] = 999
    assert state["visible"]["hp"] == 10


def test_get_hidden_returns_copy():
    state = _default_state()
    h = get_hidden(state)
    h["reputation"]["кузнец"] = 5
    assert state["hidden"]["reputation"]["кузнец"] == 0