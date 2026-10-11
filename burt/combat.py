"""
Бой — §23 ТЗ v0.7.0.

Порядок раунда:
  1. Free strike (если инициатива врага, первый раунд):
     каждый живой враг бьёт по таблице атаки. Блока нет.
  2. Ход Бурта: attack / block / flee.
  3. Ходы врагов по очереди:
     - attack и flee: таблица атаки врага, свой бросок;
     - block: таблица блока, свой бросок, counter с 6 → тому же врагу.
  4. Раунд++.

Чистое ядро: без I/O, без asyncio, без LLM.
Кубики бросает rng — функция, возвращающая 1..6.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from burt import dice
from burt.bestiary import ENEMIES, Enemy

Rng = Callable[[], int]


# ─── Данные ────────────────────────────────────────────────

@dataclass
class EnemyInstance:
    """Конкретный враг в бою."""

    id: str
    key: str
    hp: int
    hp_max: int
    mp: int = 0
    mp_max: int = 0
    alive: bool = True

    # Дракон.
    turns_taken: int = 0
    breaths_used: int = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.key,
            "hp": self.hp,
            "hp_max": self.hp_max,
            "mp": self.mp,
            "mp_max": self.mp_max,
            "alive": self.alive,
            "turns_taken": self.turns_taken,
            "breaths_used": self.breaths_used,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EnemyInstance":
        return cls(
            id=d["id"],
            key=d["key"],
            hp=d["hp"],
            hp_max=d["hp_max"],
            mp=d.get("mp", 0),
            mp_max=d.get("mp_max", 0),
            alive=d.get("alive", True),
            turns_taken=d.get("turns_taken", 0),
            breaths_used=d.get("breaths_used", 0),
        )


@dataclass
class CombatState:
    enemies: list[EnemyInstance]
    initiative: str
    free_strike_done: bool = False
    round: int = 1
    active: bool = True

    def to_dict(self) -> dict:
        return {
            "enemies": [e.to_dict() for e in self.enemies],
            "initiative": self.initiative,
            "free_strike_done": self.free_strike_done,
            "round": self.round,
            "active": self.active,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CombatState":
        return cls(
            enemies=[EnemyInstance.from_dict(e) for e in d["enemies"]],
            initiative=d["initiative"],
            free_strike_done=d.get("free_strike_done", False),
            round=d.get("round", 1),
            active=d.get("active", True),
        )


@dataclass
class BurtStats:
    """Срез Бурта для боя. Собирает оркестратор."""

    hp: int
    hp_max: int
    mp: int = 0
    mp_max: int = 0
    damage_min: int = 1
    damage_max: int = 2
    master: int = 0
    modifier: int = 0
    spells_available: bool = False


@dataclass
class RoundResult:
    combat: CombatState
    burt: BurtStats
    events_llm: list[str] = field(default_factory=list)
    events_tech: list[str] = field(default_factory=list)
    outcome: str = "ongoing"


# ─── Создание боя ──────────────────────────────────────────

def start_combat(enemy_keys: list[str], initiative: str) -> CombatState:
    if not enemy_keys:
        raise ValueError("enemy_keys must not be empty")
    if initiative not in ("burt", "enemy"):
        raise ValueError(f"invalid initiative: {initiative!r}")

    counters: dict[str, int] = {}
    enemies: list[EnemyInstance] = []
    for key in enemy_keys:
        template = ENEMIES.get(key)
        if template is None:
            raise ValueError(f"unknown enemy: {key!r}")
        counters[key] = counters.get(key, 0) + 1
        enemies.append(EnemyInstance(
            id=f"{key}_{counters[key]}",
            key=key,
            hp=template.hp_max,
            hp_max=template.hp_max,
            mp=template.mp_max,
            mp_max=template.mp_max,
        ))

    return CombatState(
        enemies=enemies,
        initiative=initiative,
        free_strike_done=(initiative != "enemy"),
    )


# ─── Помощники ─────────────────────────────────────────────

def _alive(combat: CombatState) -> list[EnemyInstance]:
    return [e for e in combat.enemies if e.alive]


def _find(combat: CombatState, enemy_id: str) -> EnemyInstance:
    for e in combat.enemies:
        if e.id == enemy_id:
            return e
    raise ValueError(f"no enemy with id {enemy_id!r}")


def _template(enemy: EnemyInstance) -> Enemy:
    return ENEMIES[enemy.key]


def _kill(enemy: EnemyInstance) -> None:
    enemy.hp = 0
    enemy.alive = False


# ─── Ход Бурта ─────────────────────────────────────────────

def _burt_attack(
    combat: CombatState,
    burt: BurtStats,
    target_id: str,
    rng: Rng,
    events_llm: list[str],
    events_tech: list[str],
) -> BurtStats:
    target = _find(combat, target_id)
    if not target.alive:
        raise ValueError(f"target {target_id!r} is not alive")

    roll = rng()
    result = dice.resolve_attack(
        roll, burt.damage_min, burt.damage_max,
        master=burt.master, modifier=burt.modifier,
    )
    events_tech.append(
        f"burt attack {target_id}: roll={roll} hit={result.hit} "
        f"dmg={result.damage} self_penalty={result.self_penalty_hp}"
    )

    name = _template(target).name
    if result.hit:
        target.hp -= result.damage
        if target.hp <= 0:
            _kill(target)
            events_llm.append(f"Ты убил {name}.")
        else:
            events_llm.append(f"Ты ударил {name}.")
    else:
        events_llm.append(f"Ты промахнулся по {name}.")

    return replace(burt, hp=burt.hp - result.self_penalty_hp)


def _burt_block(
    events_llm: list[str],
    events_tech: list[str],
) -> None:
    events_llm.append("Ты встал в защиту.")
    events_tech.append("burt action: block")


def _burt_flee(
    combat: CombatState,
    burt: BurtStats,
    rng: Rng,
    events_llm: list[str],
    events_tech: list[str],
) -> tuple[BurtStats, str]:
    # Из боя с драконом бежать нельзя.
    if any(_template(e).tags and "no_flee" in _template(e).tags
           for e in _alive(combat)):
        raise ValueError("cannot flee from dragon")

    roll = rng()
    first = _alive(combat)[0]
    t = _template(first)

    if roll in (3, 4):
        # На каждого живого врага — свой hit_roll.
        total_incoming = 0
        for enemy in _alive(combat):
            hit_roll = rng()
            res = dice.resolve_flee(
                roll,
                incoming_min=t.damage_min,
                incoming_max=t.damage_max,
                hit_roll=hit_roll,
            )
            total_incoming += res.incoming_damage
            events_tech.append(
                f"flee hit_roll vs {enemy.id}: {hit_roll} "
                f"→ {res.incoming_damage}"
            )
        events_tech.append(f"flee roll={roll} escaped=True")
        events_llm.append("Ты убежал.")
        return replace(burt, hp=burt.hp - total_incoming), "burt_fled"

    res = dice.resolve_flee(
        roll,
        incoming_min=t.damage_min,
        incoming_max=t.damage_max,
        counter_min=t.damage_min,
        counter_max=t.damage_max,
    )
    events_tech.append(
        f"flee roll={roll} escaped={res.escaped} "
        f"incoming={res.incoming_damage} counter={res.counter_damage}"
    )

    if res.escaped:
        if res.counter_damage:
            target = _alive(combat)[0]
            target.hp -= res.counter_damage
            if target.hp <= 0:
                _kill(target)
        events_llm.append("Ты убежал.")
        return replace(burt, hp=burt.hp - res.incoming_damage), "burt_fled"

    events_llm.append("Не удалось убежать.")
    return replace(burt, hp=burt.hp - res.incoming_damage), "ongoing"


# ─── Ход врага ─────────────────────────────────────────────

def _enemy_spell(
    enemy: EnemyInstance,
    template: Enemy,
    burt: BurtStats,
    rng: Rng,
    block_roll: Optional[int],
    events_llm: list[str],
    events_tech: list[str],
) -> BurtStats:
    spell_min = template.spell_damage_min
    spell_max = template.spell_damage_max

    if block_roll is not None:
        block = dice.resolve_block(
            block_roll, spell_min, spell_max,
            counter_min=spell_min, counter_max=spell_max,
        )
        enemy.mp -= template.spell_cost
        events_tech.append(
            f"{enemy.id} spell vs block: roll={block_roll} "
            f"incoming={block.incoming_damage} "
            f"self_penalty={block.self_penalty_hp} "
            f"counter={block.counter_damage}"
        )
        if block.counter_damage:
            enemy.hp -= block.counter_damage
            if enemy.hp <= 0:
                _kill(enemy)
        events_llm.append(f"{template.name} швыряет огонь, ты защищаешься.")
        return replace(
            burt,
            hp=burt.hp - block.incoming_damage - block.self_penalty_hp,
        )

    roll = rng()
    attack = dice.resolve_attack(roll, spell_min, spell_max)
    enemy.mp -= template.spell_cost
    events_tech.append(
        f"{enemy.id} spell: roll={roll} hit={attack.hit} "
        f"dmg={attack.damage} mp={enemy.mp}"
    )
    if not attack.hit:
        events_llm.append(f"{template.name} промахнулся огнём.")
        return burt
    events_llm.append(f"{template.name} швыряет огонь.")
    return replace(burt, hp=burt.hp - attack.damage)


def _enemy_melee(
    enemy: EnemyInstance,
    template: Enemy,
    burt: BurtStats,
    rng: Rng,
    block_roll: Optional[int],
    events_llm: list[str],
    events_tech: list[str],
) -> BurtStats:
    if block_roll is not None:
        block = dice.resolve_block(
            block_roll,
            template.damage_min,
            template.damage_max,
            counter_min=template.damage_min,
            counter_max=template.damage_max,
        )
        events_tech.append(
            f"block vs {enemy.id}: roll={block_roll} "
            f"incoming={block.incoming_damage} "
            f"self_penalty={block.self_penalty_hp} "
            f"counter={block.counter_damage}"
        )
        if block.counter_damage:
            enemy.hp -= block.counter_damage
            if enemy.hp <= 0:
                _kill(enemy)
        events_llm.append(f"{template.name} бьёт, ты защищаешься.")
        return replace(
            burt,
            hp=burt.hp - block.incoming_damage - block.self_penalty_hp,
        )

    roll = rng()
    modifier = -1 if "staff_penalty" in template.tags else 0
    attack = dice.resolve_attack(
        roll, template.damage_min, template.damage_max,
        master=0, modifier=modifier,
    )
    events_tech.append(
        f"{enemy.id} attack: roll={roll} modifier={modifier} "
        f"hit={attack.hit} dmg={attack.damage}"
    )
    if not attack.hit:
        events_llm.append(f"{template.name} промахнулся.")
        return burt
    events_llm.append(f"{template.name} наносит тебе удар.")
    return replace(burt, hp=burt.hp - attack.damage)


def _enemy_melee(
    enemy: EnemyInstance,
    template: Enemy,
    burt: BurtStats,
    rng: Rng,
    block_roll: Optional[int],
    events_llm: list[str],
    events_tech: list[str],
) -> BurtStats:
    if block_roll is not None:
        block = dice.resolve_block(
            block_roll,
            template.damage_min,
            template.damage_max,
            counter_min=template.damage_min,
            counter_max=template.damage_max,
        )
        events_tech.append(
            f"block vs {enemy.id}: roll={block_roll} "
            f"incoming={block.incoming_damage} counter={block.counter_damage}"
        )
        if block.counter_damage:
            enemy.hp -= block.counter_damage
            if enemy.hp <= 0:
                _kill(enemy)
        events_llm.append(f"{template.name} бьёт, ты защищаешься.")
        return replace(
            burt,
            hp=burt.hp - block.incoming_damage - block.self_penalty_hp,
        )

    roll = rng()
    modifier = -1 if "staff_penalty" in template.tags else 0
    attack = dice.resolve_attack(
        roll, template.damage_min, template.damage_max,
        master=0, modifier=modifier,
    )
    events_tech.append(
        f"{enemy.id} attack: roll={roll} modifier={modifier} "
        f"hit={attack.hit} dmg={attack.damage}"
    )
    if not attack.hit:
        events_llm.append(f"{template.name} промахнулся.")
        return burt
    events_llm.append(f"{template.name} наносит тебе удар.")
    return replace(burt, hp=burt.hp - attack.damage)


def _enemy_turn(
    enemy: EnemyInstance,
    burt: BurtStats,
    rng: Rng,
    block_roll: Optional[int],
    events_llm: list[str],
    events_tech: list[str],
) -> BurtStats:
    template = _template(enemy)

    # Шаман: каст, пока MP > 0.
    if template.spell_damage_min is not None and enemy.mp > 0:
        return _enemy_spell(
            enemy, template, burt, rng, block_roll, events_llm, events_tech,
        )

    # Дракон: дыхание на turns_taken 0, 3, 6 (пока breaths_used < max).
    use_breath = (
        template.breath_max > 0
        and enemy.turns_taken % 3 == 0
        and enemy.breaths_used < template.breath_max
    )
    if use_breath:
        enemy.breaths_used += 1
        roll = rng()
        attack = dice.resolve_attack(
            roll,
            template.breath_damage_min,
            template.breath_damage_max,
        )
        events_tech.append(
            f"{enemy.id} breath: roll={roll} hit={attack.hit} "
            f"dmg={attack.damage}"
        )
        if not attack.hit:
            events_llm.append("Дракон промахнулся дыханием.")
            return burt
        events_llm.append("Дракон дышит огнём.")
        return replace(burt, hp=burt.hp - attack.damage)

    return _enemy_melee(
        enemy, template, burt, rng, block_roll, events_llm, events_tech,
    )


# ─── Раунд ─────────────────────────────────────────────────

def resolve_round(
    combat: CombatState,
    burt: BurtStats,
    action: str,
    target_id: Optional[str],
    rng: Rng,
) -> RoundResult:
    events_llm: list[str] = []
    events_tech: list[str] = []

    if not combat.active:
        return RoundResult(combat=combat, burt=burt, outcome="ongoing")

    # Free strike.
    if combat.initiative == "enemy" and not combat.free_strike_done:
        events_llm.append("Засада!")
        for enemy in _alive(combat):
            if burt.hp <= 0:
                break
            burt = _enemy_turn(
                enemy, burt, rng, block_roll=None,
                events_llm=events_llm, events_tech=events_tech,
            )
        combat.free_strike_done = True
        if burt.hp <= 0:
            combat.active = False
            return RoundResult(
                combat=combat, burt=burt,
                events_llm=events_llm, events_tech=events_tech,
                outcome="burt_died",
            )

    # Ход Бурта.
    outcome = "ongoing"
    block_chosen = False

    if action == "attack":
        if target_id is None:
            raise ValueError("target_id is required for attack")
        burt = _burt_attack(
            combat, burt, target_id, rng, events_llm, events_tech,
        )
    elif action == "block":
        block_chosen = True
        _burt_block(events_llm, events_tech)
    elif action == "flee":
        burt, outcome = _burt_flee(
            combat, burt, rng, events_llm, events_tech,
        )
    else:
        raise ValueError(f"unknown action: {action!r}")

    if outcome == "burt_fled":
        combat.active = False
        return RoundResult(
            combat=combat, burt=burt,
            events_llm=events_llm, events_tech=events_tech,
            outcome="burt_fled",
        )

    if not _alive(combat):
        combat.active = False
        return RoundResult(
            combat=combat, burt=burt,
            events_llm=events_llm, events_tech=events_tech,
            outcome="burt_won",
        )

    # Побег не удался, но враг уже ударил внутри _burt_flee.
    # Фаза ходов врагов пропускается.
    if action == "flee":
        combat.round += 1
        return RoundResult(
            combat=combat, burt=burt,
            events_llm=events_llm, events_tech=events_tech,
            outcome="ongoing",
        )

    # Ходы врагов.
    for enemy in _alive(combat):
        if burt.hp <= 0:
            break
        block_roll = rng() if block_chosen else None
        burt = _enemy_turn(
            enemy, burt, rng, block_roll=block_roll,
            events_llm=events_llm, events_tech=events_tech,
        )
        enemy.turns_taken += 1

    # Итог.
    if burt.hp <= 0:
        combat.active = False
        return RoundResult(
            combat=combat, burt=burt,
            events_llm=events_llm, events_tech=events_tech,
            outcome="burt_died",
        )

    if not _alive(combat):
        combat.active = False
        return RoundResult(
            combat=combat, burt=burt,
            events_llm=events_llm, events_tech=events_tech,
            outcome="burt_won",
        )

    combat.round += 1
    return RoundResult(
        combat=combat, burt=burt,
        events_llm=events_llm, events_tech=events_tech,
        outcome="ongoing",
    )