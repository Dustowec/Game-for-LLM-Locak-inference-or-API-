"""
Лут с врагов — §22 ТЗ v0.7.0.

Чистое ядро: без I/O, без asyncio, без LLM.
Кубики бросает оркестратор, сюда приходит результат.

Формат дропа — LootDrop:
  items         — список {"name": str, "count": int},
                  совместимый с инвентарём state.
  coins_copper  — медяки, оркестратор кладёт в кошелёк.

Дракон выдаёт весь лут без кубика (§22).
При бегстве Бурта лута нет — решает оркестратор, не loot.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ─── Результат ─────────────────────────────────────────────

@dataclass
class LootDrop:
    """Добыча с одного или нескольких убитых врагов."""

    items: list[dict] = field(default_factory=list)
    coins_copper: int = 0


# ─── Валидация ─────────────────────────────────────────────

def _validate_roll(roll: int) -> None:
    if not isinstance(roll, int) or not 1 <= roll <= 6:
        raise ValueError(f"roll must be int in 1..6, got {roll!r}")


# ─── Таблицы лута — §22 ────────────────────────────────────

_ANIMALS: frozenset[str] = frozenset({"wolf", "boar", "bear"})


# ─── Броски по таблицам ────────────────────────────────────

def _loot_goblin(roll: int) -> LootDrop:
    if roll <= 4:
        return LootDrop()
    return LootDrop(items=[{"name": "кинжал гоблина", "count": 1}])


def _loot_goblin_shaman(roll: int) -> LootDrop:
    if roll <= 4:
        return LootDrop()
    return LootDrop(items=[{"name": "колдовской посох гоблина", "count": 1}])


def _loot_bandit(roll: int) -> LootDrop:
    if roll <= 2:
        return LootDrop(items=[{"name": "повязка", "count": 1}])
    if roll <= 4:
        return LootDrop(coins_copper=5)
    return LootDrop(items=[{"name": "меч низкого качества", "count": 1}])


def _loot_animal(roll: int) -> LootDrop:
    if roll <= 3:
        return LootDrop()
    if roll <= 5:
        return LootDrop(items=[{"name": "клыки", "count": 2}])
    return LootDrop(items=[{"name": "шкура", "count": 1}])


def _loot_dragon(roll: int) -> LootDrop:
    # Кубик игнорируется. Дракон выдаёт всё.
    return LootDrop(
        items=[
            {"name": "чешуя дракона", "count": 1},
            {"name": "драконьи клыки", "count": 2},
            {"name": "кость дракона", "count": 1},
        ]
    )


# ─── Диспетчер ─────────────────────────────────────────────

def roll_loot(enemy_key: str, roll: int) -> LootDrop:
    """
    Лут с одного врага.

    Дракон — без кубика (roll игнорируется, но валидируется).
    Неизвестный враг — пустой дроп, не ошибка.
    """
    _validate_roll(roll)

    if enemy_key == "goblin":
        return _loot_goblin(roll)
    if enemy_key == "goblin_shaman":
        return _loot_goblin_shaman(roll)
    if enemy_key == "bandit":
        return _loot_bandit(roll)
    if enemy_key in _ANIMALS:
        return _loot_animal(roll)
    if enemy_key == "dragon":
        return _loot_dragon(roll)

    return LootDrop()


# ─── Свод по нескольким врагам ─────────────────────────────

def collect_loot(enemy_keys: list[str], rolls: list[int]) -> LootDrop:
    """
    Лут со всех убитых врагов.

    enemy_keys и rolls — параллельные списки, длины должны совпадать.
    items конкатенируются в порядке врагов, coins_copper суммируется.

    Вызывается только при полной победе (все враги убиты).
    При бегстве Бурта лута нет — это решает оркестратор.
    """
    if len(enemy_keys) != len(rolls):
        raise ValueError(
            f"enemy_keys ({len(enemy_keys)}) and rolls ({len(rolls)}) "
            f"must have equal length"
        )

    result = LootDrop()
    for enemy_key, roll in zip(enemy_keys, rolls):
        drop = roll_loot(enemy_key, roll)
        result.items.extend(drop.items)
        result.coins_copper += drop.coins_copper
    return result