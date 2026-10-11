"""Кубик и таблицы §10 ТЗ v0.7.0.

Имплементация под tests/test_dice.py.
Все решения — детерминированные, рандом только в roll_d6().
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------
# Бросок
# ---------------------------------------------------------------------

def roll_d6() -> int:
    """Один бросок 1d6. Единственное место с рандомом."""
    return random.randint(1, 6)


def _clamp(value: int, lo: int = 1, hi: int = 6) -> int:
    return max(lo, min(hi, value))


def _validate_roll(roll: int) -> None:
    if not isinstance(roll, int) or not 1 <= roll <= 6:
        raise ValueError(f"roll must be int in 1..6, got {roll!r}")


# ---------------------------------------------------------------------
# Результаты
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class AttackResult:
    hit: bool
    damage: int
    self_penalty_hp: int = 0


@dataclass(frozen=True)
class BlockResult:
    incoming_damage: int
    counter_damage: int = 0
    self_penalty_hp: int = 0


@dataclass(frozen=True)
class DialogResult:
    result: str  # "fail" | "neutral" | "success"


@dataclass(frozen=True)
class DialogSecondResult:
    penalty_hp: bool = False
    angry: bool = False
    bonus: bool = False


@dataclass(frozen=True)
class MovementResult:
    result: str  # "fail_bad" | "fail" | "normal" | "good" | "great"


@dataclass(frozen=True)
class SearchResult:
    result: str  # "fail_penalty" | "fail" | "partial" | "success" | "crit"


@dataclass(frozen=True)
class CraftResult:
    result: str  # "fail" | "success" | "perfect"


@dataclass(frozen=True)
class RandomEventResult:
    result: str  # "bad" | "nothing" | "good"


@dataclass(frozen=True)
class FleeResult:
    escaped: bool
    incoming_damage: int = 0
    counter_damage: int = 0


# ---------------------------------------------------------------------
# Атака — §10
# ---------------------------------------------------------------------
# 1 — промах + −1 HP
# 2 — промах
# 3 — минимальный урон
# 4 — средний урон (при узком пуле = минимальный)
# 5 — максимальный урон
# 6 — урон ×2
#
# Порядок: модификатор сдвигает эфф. рол,
# мастерство применяется к эфф. ролу.
# Мастерство работает при modifier >= 0.
# При modifier < 0 мастерство отключается:
# «штраф возвращает промахи» (§8).
# ---------------------------------------------------------------------

def resolve_attack(
    roll: int,
    damage_min: int,
    damage_max: int,
    master: int = 0,
    modifier: int = 0,
) -> AttackResult:
    _validate_roll(roll)
    if damage_min < 0 or damage_max < 0:
        raise ValueError("damage values must be non-negative")
    if damage_min > damage_max:
        raise ValueError(
            f"damage_min ({damage_min}) > damage_max ({damage_max})"
        )

    eff_roll = _clamp(roll + modifier)
    effective_master = master if modifier >= 0 else 0

    # Промахи
    if eff_roll == 1:
        if effective_master >= 10:
            return AttackResult(hit=True, damage=damage_min)
        if effective_master >= 5:
            return AttackResult(hit=False, damage=0)
        return AttackResult(hit=False, damage=0, self_penalty_hp=1)

    if eff_roll == 2:
        if effective_master >= 10:
            return AttackResult(hit=True, damage=damage_min)
        return AttackResult(hit=False, damage=0)

    # Урон
    narrow_pool = (damage_max - damage_min) < 2

    if eff_roll == 3:
        return AttackResult(hit=True, damage=damage_min)

    if eff_roll == 4:
        if narrow_pool:
            return AttackResult(hit=True, damage=damage_min)
        return AttackResult(hit=True, damage=(damage_min + damage_max) // 2)

    if eff_roll == 5:
        return AttackResult(hit=True, damage=damage_max)

    # eff_roll == 6
    return AttackResult(hit=True, damage=damage_max * 2)


# ---------------------------------------------------------------------
# Блок / уклонение — §10
# ---------------------------------------------------------------------
# 1 — провал + макс входящий + −1 HP
# 2 — провал + макс входящий
# 3 — входящий средний
# 4 — входящий минимальный
# 5 — входящий ноль
# 6 — ноль + ответный средний (бесплатно)
# ---------------------------------------------------------------------

def resolve_block(
    roll: int,
    incoming_min: int,
    incoming_max: int,
    counter_min: Optional[int] = None,
    counter_max: Optional[int] = None,
) -> BlockResult:
    _validate_roll(roll)
    if incoming_min < 0 or incoming_max < 0:
        raise ValueError("incoming damage values must be non-negative")
    if incoming_min > incoming_max:
        raise ValueError(
            f"incoming_min ({incoming_min}) > incoming_max ({incoming_max})"
        )

    if roll == 1:
        return BlockResult(incoming_damage=incoming_max, self_penalty_hp=1)

    if roll == 2:
        return BlockResult(incoming_damage=incoming_max)

    if roll == 3:
        avg = (incoming_min + incoming_max) // 2
        return BlockResult(incoming_damage=avg)

    if roll == 4:
        return BlockResult(incoming_damage=incoming_min)

    if roll == 5:
        return BlockResult(incoming_damage=0)

    # roll == 6
    counter = 0
    if counter_min is not None and counter_max is not None:
        if counter_min > counter_max:
            raise ValueError(
                f"counter_min ({counter_min}) > counter_max ({counter_max})"
            )
        counter = (counter_min + counter_max) // 2
    return BlockResult(incoming_damage=0, counter_damage=counter)


# ---------------------------------------------------------------------
# Диалог — пары §12
# ---------------------------------------------------------------------

def resolve_dialog(roll: int, modifier: int = 0) -> DialogResult:
    _validate_roll(roll)
    eff = _clamp(roll + modifier)
    if eff <= 2:
        return DialogResult("fail")
    if eff <= 4:
        return DialogResult("neutral")
    return DialogResult("success")


def resolve_dialog_second_roll(roll: int, kind: str) -> DialogSecondResult:
    _validate_roll(roll)

    if kind == "fail":
        if roll <= 3:
            return DialogSecondResult(penalty_hp=True, angry=True)
        return DialogSecondResult()

    if kind == "success":
        if roll <= 3:
            return DialogSecondResult(bonus=True)
        return DialogSecondResult()

    raise ValueError(f"invalid kind: {kind!r}")


# ---------------------------------------------------------------------
# Движение по миру — §10
# ---------------------------------------------------------------------
# 1 — провал + плохое событие
# 2 — провал без штрафа
# 3, 4 — нормально
# 5 — хорошо
# 6 — отлично + положительное событие
# ---------------------------------------------------------------------

def resolve_movement(roll: int) -> MovementResult:
    _validate_roll(roll)
    if roll == 1:
        return MovementResult("fail_bad")
    if roll == 2:
        return MovementResult("fail")
    if roll in (3, 4):
        return MovementResult("normal")
    if roll == 5:
        return MovementResult("good")
    return MovementResult("great")


# ---------------------------------------------------------------------
# Поиск — §14
# ---------------------------------------------------------------------

def resolve_search(roll: int) -> SearchResult:
    _validate_roll(roll)
    if roll == 1:
        return SearchResult("fail_penalty")
    if roll == 2:
        return SearchResult("fail")
    if roll in (3, 4):
        return SearchResult("partial")
    if roll == 5:
        return SearchResult("success")
    return SearchResult("crit")


# ---------------------------------------------------------------------
# Крафт — §10
# ---------------------------------------------------------------------

def resolve_craft(roll: int) -> CraftResult:
    _validate_roll(roll)
    if roll in (1, 2):
        return CraftResult("fail")
    if roll in (3, 4):
        return CraftResult("success")
    return CraftResult("perfect")


# ---------------------------------------------------------------------
# Случайные события — §10
# ---------------------------------------------------------------------

def resolve_random_event(roll: int) -> RandomEventResult:
    _validate_roll(roll)
    if roll in (1, 2):
        return RandomEventResult("bad")
    if roll in (3, 4):
        return RandomEventResult("nothing")
    return RandomEventResult("good")


# ---------------------------------------------------------------------
# Побег — §23
# ---------------------------------------------------------------------
# 1 — провал + враг бьёт бесплатно макс
# 2 — провал + враг бьёт бесплатно мин
# 3-4 — ушёл, но враг может ударить (hit_roll >= 4)
# 5 — ушёл
# 6 — ушёл + нанёс врагу мин
# ---------------------------------------------------------------------

def resolve_flee(
    roll: int,
    incoming_min: int,
    incoming_max: int,
    hit_roll: Optional[int] = None,
    counter_min: Optional[int] = None,
    counter_max: Optional[int] = None,
) -> FleeResult:
    _validate_roll(roll)
    if incoming_min < 0 or incoming_max < 0:
        raise ValueError("incoming damage values must be non-negative")
    if incoming_min > incoming_max:
        raise ValueError(
            f"incoming_min ({incoming_min}) > incoming_max ({incoming_max})"
        )

    if roll == 1:
        return FleeResult(escaped=False, incoming_damage=incoming_max)

    if roll == 2:
        return FleeResult(escaped=False, incoming_damage=incoming_min)

    if roll in (3, 4):
        if hit_roll is None:
            raise ValueError("hit_roll is required for flee roll 3-4")
        _validate_roll(hit_roll)
        damage = incoming_min if hit_roll >= 4 else 0
        return FleeResult(escaped=True, incoming_damage=damage)

    if roll == 5:
        return FleeResult(escaped=True)

    # roll == 6
    counter = 0
    if counter_min is not None:
        if counter_min < 0:
            raise ValueError("counter_min must be non-negative")
        if counter_max is not None and counter_min > counter_max:
            raise ValueError(
                f"counter_min ({counter_min}) > counter_max ({counter_max})"
            )
        counter = counter_min
    return FleeResult(escaped=True, counter_damage=counter)