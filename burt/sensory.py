"""Сенсорный отчёт §25.

Plain-text, секции в квадратных скобках. Собирается из visible state.
Ничего скрытого не протекает: цифры урона, HP врагов, механика кубика,
личность квестодателя — не здесь.

Порядок секций фиксирован:
    [STATE] [LOCATION] [HANDS] [WALLET] [SKILLS]

Пустые секции (РУКИ/КОШЕЛЁК/НАВЫКИ) выводятся со словом "empty".
Заголовок [STATE] и [LOCATION] есть всегда.

Боевой отчёт §23 — отдельная функция format_combat_report.
Она НЕ трогает format_sensory_report (5 секций) и работает
от CombatState + BurtStats.
"""
from __future__ import annotations

import config
from burt.combat import CombatState, BurtStats, EnemyInstance
from burt.bestiary import ENEMIES

__all__ = ["format_sensory_report", "format_combat_report"]


# ---------------------------------------------------------------------
# Перевод на русский — игра на русском, модель маленькая,
# латиница в промпте её сбивает.
# ---------------------------------------------------------------------

_DIRECTIONS_RU = {
    "north": "north",
    "east": "east",
    "south": "south",
    "west": "west",
}

_EFFECTS_RU = {
    "blessed": "blessed",
    "cursed": "cursed",
}

# §5: на шаге 19 → 20 инжект "ты very tired".
# При SHOW_SLEEP_TIMER=False показываем качественно от этого порога.
_SLEEP_TIRED_AT = 19


# ---------------------------------------------------------------------
# Публичная функция
# ---------------------------------------------------------------------

def format_sensory_report(visible: dict) -> str:
    """Собрать сенсорный отчёт из visible state (§25, §30)."""
    sections = [
        _format_state(visible),
        _format_location(visible),
        _format_inventory(visible),
        _format_wallet(visible),
        _format_skills(visible),
    ]
    return "\n\n".join(sections)


# ---------------------------------------------------------------------
# [STATE]
# ---------------------------------------------------------------------

def _format_state(visible: dict) -> str:
    lines = ["[STATE]"]
    lines.append(_format_hp_mp(visible))
    lines.append(_format_hunger_sleep(visible))

    if config.SHOW_DATE:
        lines.append(f"Date: {visible['date']}")

    effects_line = _format_effects(visible.get("effects") or [])
    if effects_line is not None:
        lines.append(effects_line)

    return "\n".join(lines)


def _format_hp_mp(visible: dict) -> str:
    hp = visible["hp"]
    hp_max = visible["hp_max"]
    mp = visible["mp"]
    mp_max = visible["mp_max"]

    if config.HP_DISPLAY == "numbers":
        hp_part = f"HP: {hp}/{hp_max}"
    else:
        hp_part = f"HP: {_hp_qualitative(hp, hp_max)}"

    return f"{hp_part} | MP: {mp}/{mp_max}"


def _hp_qualitative(hp: int, hp_max: int) -> str:
    # §24: пороги 80% / 50% / 25%. Сравнение целочисленное,
    # без float — чтобы не поймать 79.999... вместо 80.
    if hp * 100 >= hp_max * 80:
        return "fine"
    if hp * 100 >= hp_max * 50:
        return "okay"
    if hp * 100 >= hp_max * 25:
        return "dangerous, low HP"
    return "critical"


def _format_hunger_sleep(visible: dict) -> str:
    hunger = "full" if visible["eat"] else "hungry"

    if config.SHOW_SLEEP_TIMER:
        sleep = f"{visible['sleep_counter']}/{config.DAY_STEPS}"
    else:
        sc = visible["sleep_counter"]
        sleep = "tired" if sc >= _SLEEP_TIRED_AT else "fresh"

    return f"Hunger: {hunger} | Sleep: {sleep}"


def _format_effects(effects: list) -> str | None:
    if not effects:
        return None
    translated = [_EFFECTS_RU.get(e, e) for e in effects]
    return "Effects: " + ", ".join(translated)


# ---------------------------------------------------------------------
# [LOCATION]
# ---------------------------------------------------------------------

def _format_location(visible: dict) -> str:
    lines = ["[LOCATION]"]
    loc = visible["location"]
    lines.append(loc["name"])

    exits = loc.get("exits") or []
    if exits:
        ru = [_DIRECTIONS_RU.get(d, d) for d in exits]
        lines.append("Exits: " + ", ".join(ru))

    return "\n".join(lines)


# ---------------------------------------------------------------------
# [HANDS]
# ---------------------------------------------------------------------

def _format_inventory(visible: dict) -> str:
    lines = ["[HANDS]"]
    items = visible.get("inventory") or []

    if not items:
        lines.append("empty")
    else:
        for it in items:
            name = _capitalize_first(it["name"])
            lines.append(f"{name} — {it['count']}pcs")

    return "\n".join(lines)


def _capitalize_first(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


# ---------------------------------------------------------------------
# [WALLET]
# ---------------------------------------------------------------------

def _format_wallet(visible: dict) -> str:
    lines = ["[WALLET]"]
    w = visible.get("wallet") or {}

    parts = []
    if w.get("gold", 0):
        parts.append(f"{w['gold']} gold")
    if w.get("silver", 0):
        parts.append(f"{w['silver']} silver")
    if w.get("copper", 0):
        parts.append(f"{w['copper']} copper")

    if not parts:
        lines.append("empty")
    else:
        lines.append(", ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------
# [SKILLS]
# ---------------------------------------------------------------------

def _format_skills(visible: dict) -> str:
    lines = ["[SKILLS]"]
    skills = visible.get("skills_visible") or []

    if not skills:
        lines.append("empty")
    else:
        for s in skills:
            lines.append(f"{s['name']} {s['level']}/{s['max']}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# [COMBAT] — §23
# ---------------------------------------------------------------------

def format_combat_report(combat: CombatState, burt: BurtStats) -> str:
    """Боевой сенсорный отчёт (§23).

    Формат:
        [COMBAT]
        Enemy: волк_1 (Dead), волк_2
        Your turn.

        attack волк_2
        block
        flee

    Правила:
    - HP врагов НЕ показываем, урон НЕ показываем.
    - Мёртвых помечаем "(Dead)".
    - Раунд и инициативу НЕ выводим (они в hidden).
    - Нумерация (волк_1, волк_2) — если врагов одного типа > 1.
      Одиночный враг или смешанные типы — без суффикса.
    - Меню собирается из реально доступных:
        attack <цель>  — по строке на каждого живого;
        block      — если есть живые;
        flee           — если есть живые и нет no_flee;
        cast        — если burt.spells_available.
    """
    type_counts: dict[str, int] = {}
    for e in combat.enemies:
        type_counts[e.key] = type_counts.get(e.key, 0) + 1

    opponents: list[str] = []
    alive: list[tuple[EnemyInstance, str]] = []
    for e in combat.enemies:
        display = _combat_display_name(e, type_counts)
        if e.alive:
            opponents.append(display)
            alive.append((e, display))
        else:
            opponents.append(f"{display} (Dead)")

    lines = ["[COMBAT]"]
    lines.append("Enemy: " + ", ".join(opponents))
    lines.append("Your turn.")

    menu = _build_combat_menu_lines(alive, burt)
    if menu:
        lines.append("")
        lines.extend(menu)

    return "\n".join(lines)


def _combat_display_name(
    enemy: EnemyInstance,
    type_counts: dict[str, int],
) -> str:
    """Имя врага для отчёта.

    Номер (_1, _2) — только если врагов этого типа > 1.
    Одиночный wolf выводится как "wolf", не "волк_1".
    """
    name = ENEMIES[enemy.key].name
    if type_counts.get(enemy.key, 1) > 1:
        parts = enemy.id.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return f"{name}_{parts[1]}"
    return name


def _is_no_flee(enemy: EnemyInstance) -> bool:
    t = ENEMIES.get(enemy.key)
    if t is None:
        return False
    tags = t.tags
    return bool(tags) and "no_flee" in tags


def _build_combat_menu_lines(
    alive: list[tuple[EnemyInstance, str]],
    burt: BurtStats,
) -> list[str]:
    """Собрать строки меню по реально доступным действиям.

    Empty, если живых врагов нет — тогда и меню нет.
    """
    if not alive:
        return []

    menu: list[str] = []
    for _, display in alive:
        menu.append(f"attack {display}")

    menu.append("block")

    any_no_flee = any(_is_no_flee(e) for e, _ in alive)
    if not any_no_flee:
        menu.append("flee")

    if burt.spells_available:
        menu.append("cast")

    return menu