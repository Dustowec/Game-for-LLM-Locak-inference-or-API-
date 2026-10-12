"""Сенсорный отчёт §25.

Plain-text, секции в квадратных скобках. Собирается из visible state.
Ничего скрытого не протекает: цифры урона, HP врагов, механика кубика,
личность квестодателя — не здесь.

Порядок секций фиксирован:
    [СОСТОЯНИЕ] [МЕСТО] [РУКИ] [КОШЕЛЁК] [НАВЫКИ]

Пустые секции (РУКИ/КОШЕЛЁК/НАВЫКИ) выводятся со словом "пусто".
Заголовок [СОСТОЯНИЕ] и [МЕСТО] есть всегда.
"""
from __future__ import annotations

import config

__all__ = ["format_sensory_report"]


# ---------------------------------------------------------------------
# Перевод на русский — игра на русском, модель маленькая,
# латиница в промпте её сбивает.
# ---------------------------------------------------------------------

_DIRECTIONS_RU = {
    "north": "север",
    "east": "восток",
    "south": "юг",
    "west": "запад",
}

_EFFECTS_RU = {
    "blessed": "благословлён",
    "cursed": "проклят",
}

# §5: на шаге 19 → 20 инжект "ты сильно устал".
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
# [СОСТОЯНИЕ]
# ---------------------------------------------------------------------

def _format_state(visible: dict) -> str:
    lines = ["[СОСТОЯНИЕ]"]
    lines.append(_format_hp_mp(visible))
    lines.append(_format_hunger_sleep(visible))

    if config.SHOW_DATE:
        lines.append(f"Дата: {visible['date']}")

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
        return "в порядке"
    if hp * 100 >= hp_max * 50:
        return "нормально"
    if hp * 100 >= hp_max * 25:
        return "опасно, мало HP"
    return "критично"


def _format_hunger_sleep(visible: dict) -> str:
    hunger = "сыт" if visible["eat"] else "голоден"

    if config.SHOW_SLEEP_TIMER:
        sleep = f"{visible['sleep_counter']}/{config.DAY_STEPS}"
    else:
        sc = visible["sleep_counter"]
        sleep = "устал" if sc >= _SLEEP_TIRED_AT else "бодр"

    return f"Голод: {hunger} | Сон: {sleep}"


def _format_effects(effects: list) -> str | None:
    if not effects:
        return None
    translated = [_EFFECTS_RU.get(e, e) for e in effects]
    return "Эффекты: " + ", ".join(translated)


# ---------------------------------------------------------------------
# [МЕСТО]
# ---------------------------------------------------------------------

def _format_location(visible: dict) -> str:
    lines = ["[МЕСТО]"]
    loc = visible["location"]
    lines.append(loc["name"])

    exits = loc.get("exits") or []
    if exits:
        ru = [_DIRECTIONS_RU.get(d, d) for d in exits]
        lines.append("Выходы: " + ", ".join(ru))

    return "\n".join(lines)


# ---------------------------------------------------------------------
# [РУКИ]
# ---------------------------------------------------------------------

def _format_inventory(visible: dict) -> str:
    lines = ["[РУКИ]"]
    items = visible.get("inventory") or []

    if not items:
        lines.append("пусто")
    else:
        for it in items:
            name = _capitalize_first(it["name"])
            lines.append(f"{name} — {it['count']}шт")

    return "\n".join(lines)


def _capitalize_first(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


# ---------------------------------------------------------------------
# [КОШЕЛЁК]
# ---------------------------------------------------------------------

def _format_wallet(visible: dict) -> str:
    lines = ["[КОШЕЛЁК]"]
    w = visible.get("wallet") or {}

    parts = []
    if w.get("gold", 0):
        parts.append(f"{w['gold']} зол.")
    if w.get("silver", 0):
        parts.append(f"{w['silver']} сер.")
    if w.get("copper", 0):
        parts.append(f"{w['copper']} мед.")

    if not parts:
        lines.append("пусто")
    else:
        lines.append(", ".join(parts))

    return "\n".join(lines)


# ---------------------------------------------------------------------
# [НАВЫКИ]
# ---------------------------------------------------------------------

def _format_skills(visible: dict) -> str:
    lines = ["[НАВЫКИ]"]
    skills = visible.get("skills_visible") or []

    if not skills:
        lines.append("пусто")
    else:
        for s in skills:
            lines.append(f"{s['name']} {s['level']}/{s['max']}")

    return "\n".join(lines)