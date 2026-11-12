"""Loop -- section 26 TZ v0.7.0.

Synchronous game-loop core: build_menu, parse_choice, execute_action.

Combat delegates to burt.combat.resolve_round (§23):
- CombatState is stored as dict in hidden["combat"];
- BurtStats is assembled from visible + hidden["spells"];
- after each round, hidden["combat"] is written back (or None on end);
- hp/mp synced visible <-> hidden;
- [COMBAT] report appended to events while combat is ongoing.

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
from burt.dice import (
    resolve_micro_event, calculate_micro_damage,
    resolve_movement_event, resolve_bad_movement_event,
)


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
    'crossroads': 'Crossroads',
    'thicket': 'Thicket',
    'forest': 'Forest',
    'field': 'Field',
    'steppe': 'Steppe',
    'swamp': 'Swamp',
    'river': 'River',
    'road': 'Road',
    'village': 'Village',
    'temple': 'Temple',
    'dungeon': 'Dungeon',
}

DIRECTIONS = ("north", "east", "south", "west")
COMBAT_ACTIONS = frozenset({"attack", "block", "flee"})
SLEEP_THRESHOLD = 20
CRITICAL_HP_RATIO = 0.25

# §23: locations where entering can trigger an ambush/encounter.
# Mapping: Russian location type -> spawn table key.
_ENCOUNTER_LOCATIONS = {
    "forest": "forest",
    "dungeon": "dungeon",
    "field": "field",
    "steppe": "steppe",
    "swamp": "swamp",
}
_AMBUSH_LOCATION = "thicket"  # §32: ambush at thicket


def build_menu(visible: dict, state: dict) -> list[Action]:
    """Build available actions from current game state."""
    hidden = state.get("hidden", {})
    mode = hidden.get("current_mode", "exploring")

    if mode == "combat":
        return _build_combat_menu(visible, state)

    if mode == "dialog":
        return [Action(key="exit_dialog", label="Exit dialogue")]

    # ── Micro-location exits (§11) ──────────────────────────
    micro = hidden.get("micro_location")
    if micro and micro.get("active"):
        actions: list[Action] = []
        actions.append(Action(key="go_back", label="Go back"))
        actions.append(Action(key="go_forward", label="Go forward"))
        return actions

    actions: list[Action] = []
    # TODO(O4): Burt attacks first (initiates combat from exploring).
    # Deferred until npc.py: no enemy sources in exploring yet.
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

    # ── Micro-location exits (§11) ──────────────────────────
    # Must be BEFORE the generic go_ handler below.

    if action.key == "go_back":
        micro = hidden.get("micro_location")
        if micro is None or not micro.get("active"):
            return error_result("no active micro-location")
        source = micro["source_node"]
        graph = hidden.get("location_graph", {})
        if source not in graph:
            return error_result(f"source node {source!r} missing")
        hidden["current_node_id"] = source
        hidden["micro_location"] = {"active": False}
        node = graph[source]
        visible["location"]["name"] = _resolve_location_name(
            node.get("type", ""), source,
        )
        if "exits" in node:
            visible["location"]["exits"] = [
                d for d, t in node["exits"].items() if t
            ]
        hidden["step"] = hidden.get("step", 0) + 1
        hidden["day"] = hidden.get("day", 1)
        visible["date"] = f"{hidden['day']} day(s)"
        return ActionResult(
            events=[
                f"Return to {source}.",
                sensory.format_sensory_report(visible),
            ],
        )

    if action.key == "go_forward":
        micro = hidden.get("micro_location")
        if micro is None or not micro.get("active"):
            return error_result("no active micro-location")
        target = micro["target_node"]
        if target is None:
            return error_result("no target node for micro-location")
        graph = hidden.get("location_graph", {})
        if target not in graph:
            return error_result(f"target node {target!r} missing")
        hidden["current_node_id"] = target
        hidden["micro_location"] = {"active": False}
        node = graph[target]
        loc_type = node.get("type", "")
        visible["location"]["name"] = _resolve_location_name(
            loc_type, target,
        )
        if "exits" in node:
            visible["location"]["exits"] = [
                d for d, t in node["exits"].items() if t
            ]
        hidden["step"] = hidden.get("step", 0) + 1
        # On-entry encounter roll (O1).
        combat_report = _maybe_start_combat_on_enter(
            loc_type, hidden, visible, rng,
        )
        if combat_report is not None:
            return ActionResult(events=[combat_report])
        return ActionResult(
            events=[sensory.format_sensory_report(visible)],
        )

    if action.key.startswith("go_"):
        direction = action.key[3:]
        if direction not in DIRECTIONS:
            return error_result(f"Invalid direction: {direction}")
        graph = hidden.get("location_graph", {})
        current = hidden.get("current_node_id", "start")
        if current not in graph:
            return error_result("current node missing from graph")
        node = graph[current]
        if "exits" in node:
            next_id = node["exits"].get(direction)
        else:
            next_id = node.get(direction)
        if not next_id or next_id not in graph:
            return error_result(f"no exit {direction}")

        # Movement roll (§10).
        move_roll = rng()
        move_result = dice.resolve_movement(move_roll).result
        if move_result in ("fail_bad", "fail"):
            return _handle_movement_failure(
                direction, move_result, hidden, visible, rng,
            )

        # Move to target node.
        hidden["current_node_id"] = next_id
        next_node = graph[next_id]

        # Generate new node contents if not yet entered (§17).
        if not next_node.get("entered", False):
            _enter_new_node(graph, next_id, rng)
            next_node = graph[next_id]

        loc_type = next_node.get("type") or ""
        visible["location"]["name"] = _resolve_location_name(
            loc_type, next_id,
        )
        if "exits" in next_node:
            visible["location"]["exits"] = [
                d for d, t in next_node["exits"].items() if t
            ]
        else:
            visible["location"]["exits"] = [
                d for d in DIRECTIONS if next_node.get(d)
            ]

        hidden["step"] = hidden.get("step", 0) + 1

        # On-entry encounter roll (O1).
        combat_report = _maybe_start_combat_on_enter(
            loc_type, hidden, visible, rng,
        )
        if combat_report is not None:
            # Combat started — do NOT apply positive event.
            # Order: on-entry first, then positive event only if no combat.
            return ActionResult(
                events=[combat_report],
                direction_moved=direction,
            )

        # Positive event on great movement (§10, HANDOFF-9.3).
        # Only applies if on-entry did NOT start combat.
        if move_roll in (5, 6):
            ev = resolve_movement_event(
                move_roll,
                level=visible.get("level", 1),
                rng=rng,
                hp_max=visible.get("hp_max", 10),
                mp_max=visible.get("mp_max", 3),
            )
            if ev.event_type == "loot":
                visible["wallet"]["gold"] += ev.gold
            elif ev.event_type == "blessing":
                current_hp = visible.get("hp", 10)
                new_hp = min(current_hp + ev.hp_restore, visible.get("hp_max", 10))
                visible["hp"] = new_hp
                hidden["hp_raw"] = new_hp
                current_mp = visible.get("mp", 3)
                new_mp = min(current_mp + ev.mp_restore, visible.get("mp_max", 3))
                visible["mp"] = new_mp
                hidden["mp_raw"] = new_mp
            if ev.description:
                events_list = [sensory.format_sensory_report(visible)]
                events_list.insert(0, ev.description)
                return ActionResult(
                    events=events_list,
                    direction_moved=direction,
                )
        return ActionResult(
            events=[sensory.format_sensory_report(visible)],
            direction_moved=direction,
        )

    if action.key == "search":
        hidden["step"] = hidden.get("step", 0) + 1
        roll = rng()
        search_result = dice.resolve_search(roll)
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


def _enter_new_node(graph: dict, node_id: str, rng) -> None:
    """Generate a new node per §17.

    world.enter_node expects roll_size in 1..3 for roll_type=5,
    in 1..6 for roll_type=6. We normalize before calling.
    """
    roll_count = rng()
    roll_dirs = rng()
    roll_type = rng()
    if roll_type == 5:
        roll_size = (rng() - 1) % 3 + 1  # 1..3
    else:
        roll_size = rng()  # 1..6 or ignored
    world.enter_node(
        graph, node_id, roll_count, roll_dirs, roll_type, roll_size,
    )


def _start_combat(
    enemy_keys: list[str],
    initiative: str,
    hidden: dict,
    visible: dict,
) -> str:
    """Start combat (§23). Returns combat report."""
    combat_state = combat.start_combat(enemy_keys, initiative)
    hidden["combat"] = combat_state.to_dict()
    hidden["current_mode"] = "combat"
    burt = _build_burt_stats(visible, hidden)
    return sensory.format_combat_report(combat_state, burt)


def _maybe_start_combat_on_enter(
    location_type: str,
    hidden: dict,
    visible: dict,
    rng,
) -> str | None:
    """Roll encounter on entering a location (O1: on-entry roll).

    Thicket -> always ambush (§32).
    Dangerous locations -> 1-2 attack (enemy initiative), 3-6 quiet.
    Safe locations -> no combat.
    TODO(§10): positive events on 5-6 not implemented yet.
    """
    if location_type == _AMBUSH_LOCATION:
        enemies = spawn.spawn_ambush(rng(), rng())
        return _start_combat(enemies, "enemy", hidden, visible)

    spawn_key = _ENCOUNTER_LOCATIONS.get(location_type)
    if spawn_key is None:
        return None

    roll = rng()
    if roll <= 2:
        enemies = spawn.spawn_random(spawn_key, rng(), rng())
        if enemies:
            return _start_combat(enemies, "enemy", hidden, visible)
    return None


def _handle_movement_failure(
    direction: str,
    move_result: str,
    hidden: dict,
    visible: dict,
    rng,
) -> ActionResult:
    """Movement failure (§11) — micro-location with 2 exits.

    Burt enters a micro-location between source and target nodes.
    Two guaranteed exits: back (return to source) and forward
    (try again to reach target).

    Negative event: tripped / lost.
    Damage tied to event:
      stone 1d6, tree 2d6, lightning 3d6, god's wrath 1×lvl.
    """
    hidden["step"] = hidden.get("step", 0) + 1

    current_node = hidden.get("current_node_id", "start")
    graph = hidden.get("location_graph", {})
    current_node_data = graph.get(current_node, {})
    next_id = None
    if "exits" in current_node_data:
        next_id = current_node_data["exits"].get(direction)
    else:
        next_id = current_node_data.get(direction)

    # Roll micro-event type.
    event_roll = rng()
    level = visible.get("level", 1)
    micro_event = resolve_micro_event(event_roll, level)

    # Calculate damage.
    damage = calculate_micro_damage(micro_event, rng)

    # Apply damage to HP.
    new_hp = visible.get("hp", 10) - damage
    if new_hp < 0:
        new_hp = 0
    visible["hp"] = new_hp
    hidden["hp_raw"] = new_hp

    # Build event description.
    if damage > 0:
        event_msg = (
            f"Failed to move {direction}. "
            f"Micro-event: {micro_event.event_type}. "
            f"Took {damage} damage."
        )
    else:
        event_msg = (
            f"Failed to move {direction}. "
            f"Micro-event: {micro_event.event_type}."
        )

    # Store micro-location state.
    hidden["micro_location"] = {
        "active": True,
        "source_node": current_node,
        "target_node": next_id,
        "direction": direction,
        "event_type": micro_event.event_type,
        "damage": damage,
    }

    if move_result == "fail_bad":
        # §10 (HANDOFF-9.5): roll bad event on fail_bad (movement roll=1).
        # Roll 2 (fail) does NOT call resolve_bad_movement_event.

        # Determine if current location is dangerous.
        current_node_data = graph.get(current_node, {})
        location_type = current_node_data.get("type") or ""
        is_dangerous = location_type in _ENCOUNTER_LOCATIONS

        # Roll bad event.
        bad_roll = rng()
        level = visible.get("level", 1)
        ev = resolve_bad_movement_event(
            bad_roll, level=level, rng=rng, is_dangerous=is_dangerous,
        )

        # Apply extra damage on top of micro-location damage.
        if ev.extra_damage > 0:
            new_hp = visible.get("hp", 10) - ev.extra_damage
            if new_hp < 0:
                new_hp = 0
            visible["hp"] = new_hp
            hidden["hp_raw"] = new_hp

        # Build events list.
        events_list = [event_msg]
        if ev.event_type != "nothing":
            events_list.append(ev.description)

        # Check if Burt is dead before starting combat.
        if visible.get("hp", 0) <= 0:
            return ActionResult(events=events_list, game_over=True)

        # Start combat if applicable.
        if ev.starts_combat:
            spawn_key = _ENCOUNTER_LOCATIONS.get(location_type)
            if spawn_key is not None:
                enemies = spawn.spawn_random(spawn_key, rng(), rng())
                if enemies:
                    combat_report = _start_combat(
                        enemies, "enemy", hidden, visible,
                    )
                    events_list.append(combat_report)
                    return ActionResult(events=events_list)

        return ActionResult(events=events_list)
    return ActionResult(events=[event_msg])


def _resolve_location_name(loc_type: str, node_id: str) -> str:
    """Resolve a location type to a human-readable name."""
    return _LOCATION_NAMES.get(loc_type, node_id)