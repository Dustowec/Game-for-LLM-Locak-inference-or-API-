"""Структура state.json — §30 ТЗ v0.7.0.

Чистые функции без I/O. Файловые операции — в burt.state_io.

Соглашения:
- create_initial_state(...) — стартовое состояние новой жизни.
- validate_state(state) — инварианты, raise ValueError при нарушении.
- get_visible(state) / get_hidden(state) — изолированные секции.

Все константы §4, §5, §9, §16 собраны здесь.
"""

from __future__ import annotations

import copy
from typing import Any

# ---------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------

ROLE_NAMES: tuple[str, ...] = (
    "торговец",
    "стражник",
    "крестьянин",
    "староста",
    "трактирщик",
    "кузнец",
    "рыбак",
    "ребёнок",
    "ветеран",
    "служитель",
    "чернокнижник",
    "маг",
)

DIRECTIONS: tuple[str, ...] = ("north", "south", "east", "west")

MAX_SKILL_LEVEL: int = 10

HUNGER_HUNGRY_AT: list[int] = [0, 10]
HUNGER_DEATH_AT: list[int] = [8, 18]

SLEEP_FORCED_AT: int = 20
DAY_STEPS: int = 20

REPUTATION_MIN: int = -10
REPUTATION_MAX: int = 10

VALID_STATES: set[str] = {"exploring", "dialog", "combat"}
VALID_ELEMENTS: set[str | None] = {None, "fire", "water", "earth", "air"}
VALID_ALIGNMENTS: set[str | None] = {None, "light", "dark"}

STARTING_LOCATION_NAME: str = "Развилка"
STARTING_NODE_ID: str = "node_start"

STARTING_HP: int = 10
STARTING_MP: int = 3
STARTING_HP_PER_LEVEL: int = 2
STARTING_MP_PER_LEVEL: int = 1

STARTING_WALLET: dict[str, int] = {"gold": 0, "silver": 5, "copper": 0}


# ---------------------------------------------------------------------
# Создание стартового состояния
# ---------------------------------------------------------------------

def create_initial_state(
    life: int,
    session_uuid: str,
    config_hash: str,
    session_started: str,
) -> dict[str, Any]:
    """Стартовое состояние новой жизни.

    life, session_uuid, config_hash, session_started — обязательны (§30).
    Возвращает полностью независимую структуру.
    """
    if not isinstance(life, int) or life < 1:
        raise ValueError(f"life must be int >= 1, got {life!r}")

    starting_graph = {
        STARTING_NODE_ID: {direction: None for direction in DIRECTIONS}
    }

    return {
        "meta": {
            "life": life,
            "day": 1,
            "step": 0,
            "session_uuid": session_uuid,
            "session_started": session_started,
            "config_hash": config_hash,
        },
        "visible": {
            "hp": STARTING_HP,
            "hp_max": STARTING_HP,
            "mp": STARTING_MP,
            "mp_max": STARTING_MP,
            "eat": False,
            "sleep_counter": 0,
            "date": "1 день",
            "effects": [],
            "location": {
                "name": STARTING_LOCATION_NAME,
                "exits": list(DIRECTIONS),
            },
            "inventory": [],
            "wallet": dict(STARTING_WALLET),
            "skills_visible": [],
            "state": "exploring",
        },
        "hidden": {
            "hp_raw": STARTING_HP,
            "mp_raw": STARTING_MP,
            "hunger_death_at": list(HUNGER_DEATH_AT),
            "sleep_forced_at": SLEEP_FORCED_AT,
            "effects_detail": [],
            "reputation": {role: 0 for role in ROLE_NAMES},
            "skills_raw": [],
            "quests_raw": [],
            "location_graph": starting_graph,
            "current_node_id": STARTING_NODE_ID,
            "npcs_here": [],
            "events_here": [],
            "has_room_tonight": False,
            "combat": None,
            "dice_log_last": [],
            "pending_events": [],
            "spells": {"element": None, "alignment": None},
            "has_staff": False,
            "teacher_found": False,
            "trained_by": [],
        },
    }


# ---------------------------------------------------------------------
# Валидация
# ---------------------------------------------------------------------

def validate_state(state: dict[str, Any]) -> None:
    """Проверяет инварианты. Raise ValueError при нарушении.

    Не мутирует вход.
    """
    if not isinstance(state, dict):
        raise ValueError("state must be dict")

    for section in ("meta", "visible", "hidden"):
        if section not in state:
            raise ValueError(f"state missing section: {section}")
        if not isinstance(state[section], dict):
            raise ValueError(f"state[{section}] must be dict")

    meta = state["meta"]
    visible = state["visible"]
    hidden = state["hidden"]

    # meta
    _require_int(meta, "life", minimum=1)
    _require_int(meta, "day", minimum=1)
    _require_int(meta, "step", minimum=0, maximum=DAY_STEPS)

    # visible: HP / MP
    _require_int(visible, "hp", minimum=0)
    _require_int(visible, "hp_max", minimum=1)
    _require_int(visible, "mp", minimum=0)
    _require_int(visible, "mp_max", minimum=0)

    if visible["hp"] > visible["hp_max"]:
        raise ValueError(
            f"visible.hp ({visible['hp']}) > hp_max ({visible['hp_max']})"
        )
    if visible["mp"] > visible["mp_max"]:
        raise ValueError(
            f"visible.mp ({visible['mp']}) > mp_max ({visible['mp_max']})"
        )

    # visible: сон
    _require_int(visible, "sleep_counter", minimum=0, maximum=SLEEP_FORCED_AT)

    # visible: state
    if visible.get("state") not in VALID_STATES:
        raise ValueError(
            f"visible.state must be one of {VALID_STATES}, "
            f"got {visible.get('state')!r}"
        )

    # visible: кошелёк
    wallet = visible.get("wallet")
    if not isinstance(wallet, dict):
        raise ValueError("visible.wallet must be dict")
    for coin in ("gold", "silver", "copper"):
        if coin not in wallet:
            raise ValueError(f"visible.wallet missing {coin}")
        if not isinstance(wallet[coin], int) or wallet[coin] < 0:
            raise ValueError(f"visible.wallet.{coin} must be int >= 0")

    # visible: локация без id
    location = visible.get("location")
    if not isinstance(location, dict):
        raise ValueError("visible.location must be dict")
    if "id" in location or "node_id" in location:
        raise ValueError("visible.location must not contain id/node_id")

    # hidden: hp_raw / mp_raw совпадают с visible
    if hidden.get("hp_raw") != visible["hp"]:
        raise ValueError(
            f"hidden.hp_raw ({hidden.get('hp_raw')}) "
            f"!= visible.hp ({visible['hp']})"
        )
    if hidden.get("mp_raw") != visible["mp"]:
        raise ValueError(
            f"hidden.mp_raw ({hidden.get('mp_raw')}) "
            f"!= visible.mp ({visible['mp']})"
        )

    # hidden: репутация
    reputation = hidden.get("reputation")
    if not isinstance(reputation, dict):
        raise ValueError("hidden.reputation must be dict")
    for role, value in reputation.items():
        if role not in ROLE_NAMES:
            raise ValueError(f"hidden.reputation unknown role: {role!r}")
        if not isinstance(value, int):
            raise ValueError(
                f"hidden.reputation[{role}] must be int, got {value!r}"
            )
        if not REPUTATION_MIN <= value <= REPUTATION_MAX:
            raise ValueError(
                f"hidden.reputation[{role}] ({value}) out of "
                f"[{REPUTATION_MIN}, {REPUTATION_MAX}]"
            )

    # hidden: spells
    spells = hidden.get("spells")
    if not isinstance(spells, dict):
        raise ValueError("hidden.spells must be dict")
    if spells.get("element") not in VALID_ELEMENTS:
        raise ValueError(
            f"hidden.spells.element must be one of {VALID_ELEMENTS}, "
            f"got {spells.get('element')!r}"
        )
    if spells.get("alignment") not in VALID_ALIGNMENTS:
        raise ValueError(
            f"hidden.spells.alignment must be one of {VALID_ALIGNMENTS}, "
            f"got {spells.get('alignment')!r}"
        )

    # hidden: граф локаций
    graph = hidden.get("location_graph")
    if not isinstance(graph, dict) or not graph:
        raise ValueError("hidden.location_graph must be non-empty dict")
    for node_id, node in graph.items():
        if not isinstance(node, dict):
            raise ValueError(
                f"hidden.location_graph[{node_id}] must be dict"
            )
        if set(node.keys()) != set(DIRECTIONS):
            raise ValueError(
                f"hidden.location_graph[{node_id}] must have "
                f"exactly directions {DIRECTIONS}, got {set(node.keys())}"
            )

    # hidden: current_node_id
    current = hidden.get("current_node_id")
    if current not in graph:
        raise ValueError(
            f"hidden.current_node_id ({current!r}) not in location_graph"
        )


def _require_int(
    d: dict[str, Any],
    key: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> None:
    if key not in d:
        raise ValueError(f"missing key: {key}")
    value = d[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be int, got {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} ({value}) < minimum ({minimum})")
    if maximum is not None and value > maximum:
        raise ValueError(f"{key} ({value}) > maximum ({maximum})")


# ---------------------------------------------------------------------
# Изоляция секций
# ---------------------------------------------------------------------

def get_visible(state: dict[str, Any]) -> dict[str, Any]:
    """Возвращает копию секции visible. Hidden не утекает."""
    if "visible" not in state:
        raise ValueError("state missing visible section")
    return copy.deepcopy(state["visible"])


def get_hidden(state: dict[str, Any]) -> dict[str, Any]:
    """Возвращает копию секции hidden. Visible не утекает."""
    if "hidden" not in state:
        raise ValueError("state missing hidden section")
    return copy.deepcopy(state["hidden"])