"""
Спавн врагов.

Источники: §21 (цифры врагов), §23 (инициатива, случайная встреча),
§32 (спавн по локациям).

Чистое ядро: без I/O, без asyncio, без LLM.
Кубики бросает оркестратор, сюда приходит результат.

Расклады кубика (1 — хуже всего, 6 — лучше всего):

  Лес:
    1-2 → гоблин-шаман (один)
    3   → гоблин (стая 1-3)
    4-5 → волк (стая 1-3)
    6   → кабан (один)

  Подземелье:
    1   → дракон
    2-3 → гоблин-шаман (один)
    4-6 → гоблин (стая 1-3)

  Поле:   кабан (один).
  Степь:  волк (стая).
  Болото: гоблин (стая).
  Река, дорога, деревня, храм: пусто.

  Размер стаи (гоблин и волк):
    1-2 → 3
    3-4 → 2
    5-6 → 1

  Засада (в кустарнике):
    1-3 → волк (стая)
    4-6 → гоблин (стая)
"""

from __future__ import annotations

from typing import Optional

# ─── Константы ─────────────────────────────────────────────

PACK_ENEMIES: frozenset[str] = frozenset({"goblin", "wolf"})

_ENCOUNTER_TABLE: dict[str, dict[int, str]] = {
    "forest": {
        1: "goblin_shaman",
        2: "goblin_shaman",
        3: "goblin",
        4: "wolf",
        5: "wolf",
        6: "boar",
    },
    "dungeon": {
        1: "dragon",
        2: "goblin_shaman",
        3: "goblin_shaman",
        4: "goblin",
        5: "goblin",
        6: "goblin",
    },
    "field": {
        1: "boar", 2: "boar", 3: "boar",
        4: "boar", 5: "boar", 6: "boar",
    },
    "steppe": {
        1: "wolf", 2: "wolf", 3: "wolf",
        4: "wolf", 5: "wolf", 6: "wolf",
    },
    "swamp": {
        1: "goblin", 2: "goblin", 3: "goblin",
        4: "goblin", 5: "goblin", 6: "goblin",
    },
}

_EMPTY_LOCATIONS: frozenset[str] = frozenset(
    {"river", "road", "village", "temple"}
)


# ─── Валидация ─────────────────────────────────────────────

def _validate_roll(roll: int, name: str = "roll") -> None:
    if not isinstance(roll, int) or not 1 <= roll <= 6:
        raise ValueError(f"{name} must be int in 1..6, got {roll!r}")


# ─── Возможные враги в локации ─────────────────────────────

def possible_enemies(location: str) -> frozenset[str]:
    """
    Множество ключей врагов, которые могут встретиться в локации.

    Для локации вне таблицы — пустое множество.
    """
    table = _ENCOUNTER_TABLE.get(location)
    if table is None:
        return frozenset()
    return frozenset(table.values())


# ─── Тип врага по кубику ───────────────────────────────────

def roll_enemy_type(location: str, roll: int) -> Optional[str]:
    """
    Ключ врага по кубику.

    Возвращает None для пустых локаций и локаций вне таблицы.
    """
    _validate_roll(roll, "roll")
    table = _ENCOUNTER_TABLE.get(location)
    if table is None:
        return None
    return table[roll]


# ─── Размер стаи ───────────────────────────────────────────

def is_pack(enemy_key: str) -> bool:
    """Может ли этот враг быть стаей."""
    return enemy_key in PACK_ENEMIES


def roll_pack_size(enemy_key: str, roll: int) -> int:
    """
    Сколько врагов этого типа в стае.

    Для стайных (гоблин, волк):
      1-2 → 3
      3-4 → 2
      5-6 → 1

    Для одиночек (шаман, кабан, дракон) — всегда 1,
    кубик игнорируется.
    """
    _validate_roll(roll, "roll")
    if not is_pack(enemy_key):
        return 1
    if roll <= 2:
        return 3
    if roll <= 4:
        return 2
    return 1


# ─── Спавн случайной встречи ───────────────────────────────

def spawn_random(
    location: str,
    roll_type: int,
    roll_size: int,
) -> list[str]:
    """
    Список ключей врагов для случайной встречи.

    roll_type — кубик на тип врага.
    roll_size — кубик на размер стаи (игнорируется для одиночек).

    Пустая локация или локация вне таблицы → [].
    """
    enemy_key = roll_enemy_type(location, roll_type)
    if enemy_key is None:
        return []
    size = roll_pack_size(enemy_key, roll_size)
    return [enemy_key] * size


# ─── Засада ────────────────────────────────────────────────

def spawn_ambush(roll_type: int, roll_size: int) -> list[str]:
    """
    Список ключей врагов для засады.

    Засада: только гоблины или только волки.
      1-3 → волк
      4-6 → гоблин

    Размер — по общему правилу стаи.
    """
    _validate_roll(roll_type, "roll_type")
    _validate_roll(roll_size, "roll_size")

    enemy_key = "wolf" if roll_type <= 3 else "goblin"
    size = roll_pack_size(enemy_key, roll_size)
    return [enemy_key] * size