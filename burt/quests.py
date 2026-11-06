"""Quest system -- section 18, 33, 36 spec v0.7.0.

Pure logic layer: no I/O, no asyncio, no LLM.
Reads/writes state dict directly. Loads templates from quests_templates.json.

Public API:
    quest_can_give(role, state) -> bool
    quest_give(quest_id, role, state) -> (ok, msg)
    quest_progress(quest_id, amount, state) -> (ok, msg)
    try_deceive(npc_role, node_id, state) -> (ok, msg)
    quest_complete(quest_id, state) -> (ok, msg)
    quest_fail(quest_id, state) -> (ok, msg)
    expire_blockades(state) -> None
    expire_deceit_penalties(state) -> None
    quest_get_active(quest_id, state) -> Quest | None
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from burt import dice


# ---------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------

@dataclass
class Quest:
    """A single quest instance."""
    id: str
    giver_role: str
    giver_node: str
    title: str
    status: str  # active | completed | failed
    type: str  # deliver | help | deceive | chain
    progress: int = 0
    required: int = 0
    deliver_items: list[dict] | None = None
    issued_day: int = 0
    deadline_day: int | None = None
    chain: str | None = None
    chain_step: int | None = None


# ---------------------------------------------------------------------
# Templates loading
# ---------------------------------------------------------------------

_templates_cache: dict | None = None


def _load_templates() -> dict:
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "quests_templates.json")
    with open(path, encoding="utf-8") as f:
        _templates_cache = json.load(f)
    return _templates_cache


# ---------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------

def _dict_to_quest(d: dict) -> Quest:
    return Quest(
        id=d["id"],
        giver_role=d["giver_role"],
        giver_node=d["giver_node"],
        title=d["title"],
        status=d["status"],
        type=d["type"],
        progress=d.get("progress", 0),
        required=d.get("required", 0),
        deliver_items=d.get("deliver_items"),
        issued_day=d.get("issued_day", 0),
        deadline_day=d.get("deadline_day"),
        chain=d.get("chain"),
        chain_step=d.get("chain_step"),
    )


def _quest_to_dict(q: Quest) -> dict:
    return {
        "id": q.id,
        "giver_role": q.giver_role,
        "giver_node": q.giver_node,
        "title": q.title,
        "status": q.status,
        "type": q.type,
        "progress": q.progress,
        "required": q.required,
        "deliver_items": q.deliver_items,
        "issued_day": q.issued_day,
        "deadline_day": q.deadline_day,
        "chain": q.chain,
        "chain_step": q.chain_step,
    }


def _find_active_deceive(state: dict) -> Quest | None:
    hidden = state.setdefault("hidden", {})
    quests_raw = hidden.get("quests_raw", [])
    for d in quests_raw:
        if d.get("status") == "active" and d.get("type") == "deceive":
            return _dict_to_quest(d)
    return None


def _apply_deliver_items(state: dict, items: list[dict]) -> None:
    visible = state.setdefault("visible", {})
    inventory = visible.get("inventory", [])
    for item_req in items:
        name = item_req["name"]
        count_needed = item_req["count"]
        for inv_item in inventory:
            if inv_item.get("name") == name:
                inv_item["count"] -= count_needed
                if inv_item["count"] <= 0:
                    inventory.remove(inv_item)
                break


def _advance_chain(q: Quest, state: dict) -> None:
    if q.chain is None:
        return
    templates = _load_templates()
    next_id = templates.get(q.id, {}).get("next_chain_step")
    if next_id is None:
        # Stub: chain finished
        return
    if next_id not in templates:
        return
    tpl = templates[next_id]
    new_q = Quest(
        id=tpl["id"],
        giver_role=q.giver_role,
        giver_node=q.giver_node,
        title=tpl["title"],
        status="active",
        type=tpl["type"],
        progress=0,
        required=tpl.get("required") or 0,
        deliver_items=tpl.get("deliver_items"),
        issued_day=q.issued_day,
        deadline_day=None,
        chain=tpl.get("chain"),
        chain_step=tpl.get("step"),
    )
    hidden = state.setdefault("hidden", {})
    hidden.setdefault("quests_raw", []).append(_quest_to_dict(new_q))


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def quest_can_give(role: str, state: dict) -> bool:
    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)
    current_node = hidden.get("current_node_id", "")

    # Check no active quest from this role
    quests_raw = hidden.get("quests_raw", [])
    for d in quests_raw:
        if d.get("giver_role") == role and d.get("status") == "active":
            return False

    # Check role not blocked
    block = hidden.get("role_quest_block", {}).get(role)
    if block is not None and block > current_day:
        return False

    # Check limit 3 per day per node
    issued = hidden.get("quests_issued_today", {}).get(current_node, 0)
    if issued >= 3:
        return False

    return True


def quest_give(quest_id: str, role: str, state: dict) -> tuple[bool, str]:
    if not quest_can_give(role, state):
        return (False, "cannot give quest")

    templates = _load_templates()
    if quest_id not in templates:
        return (False, "unknown quest")

    tpl = templates[quest_id]
    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)
    current_node = hidden.get("current_node_id", "")

    deadline = None
    dl_days = tpl.get("deadline_days")
    if dl_days is not None:
        deadline = current_day + dl_days

    q = Quest(
        id=tpl["id"],
        giver_role=role,
        giver_node=current_node,
        title=tpl["title"],
        status="active",
        type=tpl["type"],
        progress=0,
        required=tpl.get("required") or 0,
        deliver_items=tpl.get("deliver_items"),
        issued_day=current_day,
        deadline_day=deadline,
        chain=tpl.get("chain"),
        chain_step=tpl.get("step"),
    )

    hidden.setdefault("quests_issued_today", {})
    hidden["quests_issued_today"][current_node] = hidden["quests_issued_today"].get(current_node, 0) + 1
    hidden.setdefault("quests_raw", []).append(_quest_to_dict(q))
    return (True, f"Quest given: {q.title}")


def quest_progress(quest_id: str, amount: int, state: dict) -> tuple[bool, str]:
    q = quest_get_active(quest_id, state)
    if q is None:
        return (False, "no active quest")

    if q.type != "help":
        if q.type == "deliver":
            return (False, "deliver has no progress")
        if q.type == "deceive":
            return (False, "use try_deceive")
        return (False, "cannot progress this quest type")

    q.progress += amount
    hidden = state.setdefault("hidden", {})
    for d in hidden.get("quests_raw", []):
        if d.get("id") == quest_id:
            d["progress"] = q.progress
            break
    return (True, f"Progress: {q.progress}/{q.required}")


def try_deceive(npc_role: str, node_id: str, state: dict) -> tuple[bool, str]:
    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)
    key = f"{node_id}::{npc_role}"

    attempts = hidden.setdefault("quest_deceive_attempts", {})
    if key in attempts:
        return (False, "already tried to deceive this NPC")

    roll = dice.roll_d6()
    penalties = hidden.get("deceit_penalty_until", {})

    if roll >= 3:
        attempts[key] = True
        hidden["quest_deceive_attempts"] = attempts
        deceive_quest = _find_active_deceive(state)
        if deceive_quest:
            deceive_quest.progress += 1
            for d in hidden.get("quests_raw", []):
                if d.get("id") == deceive_quest.id:
                    d["progress"] = deceive_quest.progress
                    break
        return (True, "deception succeeded")
    else:
        # Cooldown check
        penalty_until = penalties.get(npc_role)
        if penalty_until is None or penalty_until <= current_day:
            reputation = hidden.setdefault("reputation", {})
            reputation[npc_role] = reputation.get(npc_role, 0) - 1
            penalties[npc_role] = current_day + 10
            hidden["deceit_penalty_until"] = penalties
        attempts[key] = True
        hidden["quest_deceive_attempts"] = attempts
        return (False, "deception failed")


def quest_complete(quest_id: str, state: dict) -> tuple[bool, str]:
    q = quest_get_active(quest_id, state)
    if q is None:
        return (False, "no active quest")

    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)

    if q.type == "deliver":
        visible = state.setdefault("visible", {})
        inventory = visible.get("inventory", [])
        deliver_items = q.deliver_items or []

        # Check full set
        can_full = True
        for item_req in deliver_items:
            name = item_req["name"]
            count_needed = item_req["count"]
            found = 0
            for inv_item in inventory:
                if inv_item.get("name") == name:
                    found = inv_item.get("count", 0)
                    break
            if found < count_needed:
                can_full = False
                break

        if can_full:
            _apply_deliver_items(state, deliver_items)
            q.status = "completed"
            for d in hidden.get("quests_raw", []):
                if d.get("id") == quest_id:
                    d["status"] = "completed"
                    break
            _advance_chain(q, state)
            return (True, "quest completed")
        else:
            # Partial: roll d6
            roll = dice.roll_d6()
            if roll <= 2:
                quest_fail(quest_id, state)
                return (False, "partial failure")
            elif roll <= 4:
                return (False, "need to finish")
            else:
                # Accept partial
                _apply_deliver_items(state, deliver_items)
                q.status = "completed"
                for d in hidden.get("quests_raw", []):
                    if d.get("id") == quest_id:
                        d["status"] = "completed"
                        break
                _advance_chain(q, state)
                return (True, "accepted partially")

    else:
        # help / deceive / chain
        if q.progress >= q.required:
            q.status = "completed"
            for d in hidden.get("quests_raw", []):
                if d.get("id") == quest_id:
                    d["status"] = "completed"
                    break
            _advance_chain(q, state)
            return (True, "quest completed")
        else:
            roll = dice.roll_d6()
            if roll <= 2:
                quest_fail(quest_id, state)
                return (False, "partial failure")
            elif roll <= 4:
                return (False, "need to finish")
            else:
                q.status = "completed"
                for d in hidden.get("quests_raw", []):
                    if d.get("id") == quest_id:
                        d["status"] = "completed"
                        break
                _advance_chain(q, state)
                return (True, "accepted partially")


def quest_fail(quest_id: str, state: dict) -> tuple[bool, str]:
    q = quest_get_active(quest_id, state)
    if q is None:
        return (False, "no active quest")

    q.status = "failed"
    hidden = state.setdefault("hidden", {})
    for d in hidden.get("quests_raw", []):
        if d.get("id") == quest_id:
            d["status"] = "failed"
            break

    giver = q.giver_role
    killed = hidden.get("killed_quest_givers", [])
    blocks = hidden.setdefault("role_quest_block", {})

    if giver in killed:
        blocks[giver] = -1
    else:
        blocks[giver] = hidden.get("day", 1) + 10
    hidden["role_quest_block"] = blocks

    return (True, "quest failed")


def expire_blockades(state: dict) -> None:
    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)
    blocks = hidden.get("role_quest_block", {})
    to_remove = []
    for role, deadline in blocks.items():
        if deadline > 0 and current_day >= deadline:
            to_remove.append(role)
    for role in to_remove:
        del blocks[role]
    hidden["role_quest_block"] = blocks


def expire_deceit_penalties(state: dict) -> None:
    hidden = state.setdefault("hidden", {})
    current_day = hidden.get("day", 1)
    penalties = hidden.get("deceit_penalty_until", {})
    to_remove = []
    for role, deadline in penalties.items():
        if current_day >= deadline:
            to_remove.append(role)
    for role in to_remove:
        del penalties[role]
    hidden["deceit_penalty_until"] = penalties


def quest_get_active(quest_id: str, state: dict) -> Quest | None:
    hidden = state.setdefault("hidden", {})
    quests_raw = hidden.get("quests_raw", [])
    for d in quests_raw:
        if d.get("id") == quest_id and d.get("status") == "active":
            return _dict_to_quest(d)
    return None
