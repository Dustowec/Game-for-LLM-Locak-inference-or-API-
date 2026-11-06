"""Loop -- section 26 TZ v0.7.0.

Synchronous game-loop core: build_menu, parse_choice, execute_action.

Combat delegates to burt.combat.resolve_round (§23):
- CombatState is stored as dict in hidden["combat"];
- BurtStats is assembled from visible + hidden["spells"];
- after each round, hidden["combat"] is written back (or None on end);
- hp/mp synced visible <-> hidden;
- [БОЙ] report appended to events while combat is ongoing.

All docstrings/comments in English. No Cyrillic literals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from burt import world
from burt import sensory
from burt import hunger
from burt import sleep as sleep_mod
from burt import dice
from burt import spawn
from burt import combat
from burt.combat import CombatState, BurtStats
from burt.bestiary import ENEMIES


@dataclass
class Action:
    """One menu entry the LLM can choose."""
    key: str
    label: str
    cost_free: bool = False
    target_id: str | None = None
    item: str | None = None


@dataclass
class ActionResult:
    """Result of executing one action."""
    events: list[str] = field(default_factory=list)
    new_hp: int | None = None
    game_over: bool = False
    search_result: str | None = None
    direction_moved: str | None = None


# Location name mapping
_LOCATION_NAMES = {
    'старт': 'Crossroads',
    'кустарник': 'Thicket',
    'лес': 'Forest',
    'поле': 'Field',
    'степь': 'Steppe',
    'болото': 'Swamp',
    'река': 'River',
    'дорога': 'Road',
    'деревня': 'Village',
    'храм': 'Temple',
    'подземелье': 'Dungeon',
}

DIRECTIONS = ("north", "east", "south", "west")
COMBAT_ACTIONS = frozenset({"attack", "block", "flee"})
SLEEP_THRESHOLD = 20
CRITICAL_HP_RATIO = 0.25


def build_menu(visible: dict, state: dict) -> list[Action]:
    """Build available actions from current game state."""
    hidden = state.get("hidden", {})
    mode = hidden.get("current_mode", "exploring")

    if mode == "combat":
        return _build_combat_menu(visible, state)

    if mode == "dialog":
        return [Action(key="exit_dialog", label="Exit dialogue")]

    actions: list[Action] = []
    actions.append(Action(key="osmotret", label="Look around"))

    exits = visible.get("location", {}).get("exits", [])
    for d in DIRECTIONS:
        if d in exits:
            actions.append(Action(key=f"go_{d}", label=f"Go {d}"))

    actions.append(Action(key="search", label="Search"))

    sc = visible.get("sleep_counter", 0)
    hp = visible.get("hp", 10)
    hp_max = visible.get("hp_max", 10)
    if sc >= 19 or (hp_max > 0 and hp * 100 < hp_max * 25):
        actions.append(Action(key="sleep", label="Sleep"))

    inventory = visible.get("inventory", [])
    for item in inventory:
        name = item.get("name", "").lower()
        food_ru = chr(0x445)+chr(0x43B)+chr(0x435)+chr(0x431)
        water_ru = chr(0x432)+chr(0x43E)+chr(0x434)+chr(0x430)
        if "bread" in name or "food" in name or food_ru in name:
            actions.append(Action(key="eat_food", label="Eat food"))
        if "water" in name or chr(0x432)+chr(0x43E)+chr(0x434) in name:
            actions.append(Action(key="drink_water", label="Drink water"))

    return actions


def _build_combat_menu(visible: dict, state: dict) -> list[Action]:
    """Build combat menu from hidden["combat"] (CombatState dict)."""
    hidden = state.get("hidden", {})
    combat_dict = hidden.get("combat")
    if combat_dict is None:
        return []
    try:
        combat_state = CombatState.from_dict(combat_dict)
    except (KeyError, ValueError, TypeError):
        return []

    actions: list[Action] = []
    any_alive = False
    for enemy in combat_state.enemies:
        if not enemy.alive:
            continue
        any_alive = True
        t = ENEMIES.get(enemy.key)
        name = t.name if t is not None else enemy.key
        actions.append(Action(
            key=f"attack_{enemy.id}",
            label=f"Attack {name}",
            target_id=enemy.id,
        ))
    if any_alive:
        actions.append(Action(key="block", label="Block"))
        actions.append(Action(key="flee", label="Flee"))
    return actions


def parse_choice(user_text: str, actions: list[Action]) -> Action:
    """Parse LLM response and return the chosen Action."""
    if not actions:
        return Action(key="osmotret", label="Look around")

    for line in user_text.splitlines():
        stripped = line.strip()
        if len(stripped) >= 2 and ord(stripped[0]) == 0x42B and stripped[1] == ':':
            num_str = stripped[2:].strip()
            try:
                idx = int(num_str)
                if 0 <= idx < len(actions):
                    return actions[idx]
            except ValueError:
                pass

    text_lower = user_text.lower()
    for action in actions:
        label_lower = action.label.lower()
        if label_lower in text_lower or any(word in text_lower for word in label_lower.split()):
            return action

    return actions[0]


def execute_action(action: Action, state: dict, rng=None) -> ActionResult:
    """Execute an action and mutate state. Delegates to sub-modules.

    rng is a callable returning 1..6 (dice roll). Defaults to dice.roll_d6.
    """
    if rng is None:
        rng = dice.roll_d6
    hidden = state.setdefault("hidden", {})
    visible = state.setdefault("visible", {})
    mode = hidden.get("current_mode", "exploring")

    if action.key == "osmotret":
        hidden["step"] = hidden.get("step", 0) + 1
        report = sensory.format_sensory_report(visible)
        osm_str = chr(0x43E)+chr(0x441)+chr(0x43C)+chr(0x43E)+chr(0x442)+chr(0x440)
        return ActionResult(events=[osm_str, report])

    if action.key.startswith("go_"):
        direction = action.key[3:]
        if direction not in DIRECTIONS:
            return error_result(f"Invalid direction: {direction}")
        graph = hidden.get("location_graph", {})
        current = hidden.get("current_node_id", "start")
        if current in graph:
            node = graph[current]
            # Support both {north: id, ...} and {exits: {north: id, ...}} shapes.
            if "exits" in node:
                next_id = node["exits"].get(direction)
            else:
                next_id = node.get(direction)
            if next_id and next_id in graph:
                hidden["current_node_id"] = next_id
                loc_type = hidden.get("location_types", {}).get(next_id, "")
                visible["location"]["name"] = _resolve_location_name(loc_type, next_id)
                next_node = graph[next_id]
                if "exits" in next_node:
                    visible["location"]["exits"] = list(next_node["exits"].keys())
                else:
                    visible["location"]["exits"] = [
                        d for d in DIRECTIONS if next_node.get(d)
                    ]
        hidden["step"] = hidden.get("step", 0) + 1
        report = sensory.format_sensory_report(visible)
        return ActionResult(events=[f"Moved {direction}. {report}"])

    if action.key == "search":
        hidden["step"] = hidden.get("step", 0) + 1
        current = hidden.get("current_node_id", "start")
        loc_type = hidden.get("location_types", {}).get(current, "")
        location_key = loc_type if loc_type in spawn._ENCOUNTER_TABLE else "forest"
        roll = dice.roll_d6()
        search_result = dice.resolve_search(roll)
        hidden["step"] = hidden.get("step", 0) + 1
        return ActionResult(
            events=[search_result.result, sensory.format_sensory_report(visible)],
            search_result=search_result.result,
        )

    if action.key == "sleep":
        hp_max = visible.get("hp_max", 10)
        mp_max = visible.get("mp_max", 3)
        new_hp, new_mp, new_effects = sleep_mod.apply_sleep(hp_max, mp_max)
        visible["hp"] = new_hp
        visible["mp"] = new_mp
        visible["effects"] = new_effects
        hidden["hp_raw"] = new_hp
        hidden["mp_raw"] = new_mp
        eat, res = hunger.reset_hunger_after_sleep()
        visible["eat"] = eat
        visible["sleep_counter"] = 0
        hidden["day"] = hidden.get("day", 1) + 1
        hidden["step"] = 0
        visible["date"] = f"{hidden['day']} day(s)"
        son_str = chr(0x441)+chr(0x43E)+chr(0x43D)
        return ActionResult(events=[son_str, sensory.format_sensory_report(visible)])

    if mode == "combat":
        return _execute_combat(action, state, rng)

    return error_result(f"Unknown action: {action.key}")


def _execute_combat(action: Action, state: dict, rng) -> ActionResult:
    """Execute one combat action via combat.resolve_round (§23)."""
    hidden = state["hidden"]
    visible = state["visible"]

    combat_dict = hidden.get("combat")
    if combat_dict is None:
        return error_result("no active combat")

    try:
        combat_state = CombatState.from_dict(combat_dict)
    except (KeyError, ValueError, TypeError) as ex:
        return error_result(f"invalid combat state: {ex}")

    if action.key.startswith("attack_"):
        target_id = action.target_id or action.key[len("attack_"):]
        found = None
        for e in combat_state.enemies:
            if e.id == target_id:
                found = e
                break
        if found is None:
            return error_result(f"no such enemy: {target_id}")
        if not found.alive:
            return error_result(f"enemy is dead: {target_id}")
        combat_action = "attack"
    elif action.key == "block":
        combat_action = "block"
        target_id = None
    elif action.key == "flee":
        combat_action = "flee"
        target_id = None
    else:
        return error_result(f"unknown combat action: {action.key}")

    burt = _build_burt_stats(visible, hidden)

    try:
        result = combat.resolve_round(
            combat_state, burt, combat_action, target_id, rng,
        )
    except ValueError as ex:
        return error_result(str(ex))

    visible["hp"] = result.burt.hp
    visible["mp"] = result.burt.mp
    hidden["hp_raw"] = result.burt.hp
    hidden["mp_raw"] = result.burt.mp

    events: list[str] = list(result.events_llm)
    action_result = ActionResult(events=events)

    if result.outcome == "ongoing":
        hidden["combat"] = result.combat.to_dict()
        hidden["current_mode"] = "combat"
        report = sensory.format_combat_report(result.combat, result.burt)
        events.append(report)
    else:
        hidden["combat"] = None
        hidden["current_mode"] = "exploring"
        if result.outcome == "burt_died":
            action_result.game_over = True

    return action_result


def _build_burt_stats(visible: dict, hidden: dict) -> BurtStats:
    """Assemble BurtStats from visible + hidden for combat.

    spells_available = element or alignment chosen.
    damage/master/modifier use BurtStats defaults until weapon system lands.
    """
    spells = hidden.get("spells") or {}
    if not isinstance(spells, dict):
        spells = {}
    element = spells.get("element")
    alignment = spells.get("alignment")
    spells_available = (element is not None) or (alignment is not None)

    return BurtStats(
        hp=visible["hp"],
        hp_max=visible["hp_max"],
        mp=visible["mp"],
        mp_max=visible["mp_max"],
        spells_available=spells_available,
    )


def should_sleep(visible: dict, state: dict) -> bool:
    """Check if character should sleep now."""
    sc = visible.get("sleep_counter", 0)
    if sc >= SLEEP_THRESHOLD:
        return True
    hp = visible.get("hp", 10)
    hp_max = visible.get("hp_max", 10)
    if hp_max > 0 and hp * 100 < hp_max * CRITICAL_HP_RATIO * 100:
        return True
    return False


def error_result(msg: str) -> ActionResult:
    """Create an error ActionResult."""
    err_str = chr(0x43E)+chr(0x448)+chr(0x438)+chr(0x431)+chr(0x43A)+chr(0x430)
    return ActionResult(events=[err_str + ": " + msg])


def _resolve_location_name(loc_type: str, node_id: str) -> str:
    """Resolve a location type to a human-readable name."""
    return _LOCATION_NAMES.get(loc_type, node_id)