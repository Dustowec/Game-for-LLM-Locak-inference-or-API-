"""
Справочник врагов — §21 ТЗ v0.7.0.

Чистые данные. Никакой логики.

Цифры врага (HP, урон, MP, дыхание) — здесь.
Логика хода врага (каст/staff, fangs/дыхание, паттерн) — в combat.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class Enemy:
    """Шаблон врага. Конкретный экземпляр в бою — копия с текущим HP."""

    key: str
    name: str
    hp_max: int
    damage_min: int
    damage_max: int
    weapon: str = ""

    # Для шамана: огненный шар.
    mp_max: int = 0
    spell_damage_min: Optional[int] = None
    spell_damage_max: Optional[int] = None
    spell_cost: Optional[int] = None

    # Для дракона: дыхание.
    breath_damage_min: Optional[int] = None
    breath_damage_max: Optional[int] = None
    breath_max: int = 0

    # Ярлыки для combat.py:
    #   pack          — может быть стаей (wolf)
    #   passive       — не атакует сам (bear)
    #   no_flee       — из боя нельзя убежать (dragon)
    #   wounded_prey  — атакует только раненого Бурта (boar)
    #   staff_penalty — staff даёт штраф −1 к броску (шаман)
    tags: frozenset[str] = field(default_factory=frozenset)


ENEMIES: dict[str, Enemy] = {
    "goblin": Enemy(
        key="goblin",
        name="goblin",
        hp_max=6,
        damage_min=1,
        damage_max=2,
        weapon="goblin_dagger",
    ),
    "goblin_shaman": Enemy(
        key="goblin_shaman",
        name="goblin_shaman",
        hp_max=8,
        damage_min=0,
        damage_max=1,
        weapon="goblin_staff",
        mp_max=5,
        spell_damage_min=3,
        spell_damage_max=6,
        spell_cost=1,
        tags=frozenset({"staff_penalty"}),
    ),
    "wolf": Enemy(
        key="wolf",
        name="wolf",
        hp_max=8,
        damage_min=1,
        damage_max=3,
        weapon="fangs",
        tags=frozenset({"pack"}),
    ),
    "boar": Enemy(
        key="boar",
        name="boar",
        hp_max=12,
        damage_min=1,
        damage_max=3,
        weapon="fangs",
        tags=frozenset({"wounded_prey"}),
    ),
    "bandit": Enemy(
        key="bandit",
        name="bandit",
        hp_max=10,
        damage_min=2,
        damage_max=4,
        weapon="sword",
    ),
    "bear": Enemy(
        key="bear",
        name="bear",
        hp_max=18,
        damage_min=5,
        damage_max=9,
        weapon="claws_and_teeth",
        tags=frozenset({"passive"}),
    ),
    "dragon": Enemy(
        key="dragon",
        name="dragon",
        hp_max=60,
        damage_min=16,
        damage_max=22,
        weapon="fangs",
        breath_damage_min=12,
        breath_damage_max=18,
        breath_max=3,
        tags=frozenset({"no_flee"}),
    ),
}