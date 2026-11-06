"""
Тесты для burt/combat.py.

Порядок раунда:
  1. Free strike (если инициатива врага, раунд 1): каждый живой враг
     бьёт по таблице атаки. Блока нет, реакции нет.
  2. Ход Бурта: attack (1 бросок), block (0 бросков, ставит флаг),
     flee (1 бросок + hit_roll на каждого, если 3-4).
  3. Ходы врагов по очереди:
     - если Бурт атаковал: таблица атаки, свой бросок на каждого;
     - если Бурт блокировал: таблица блока, свой бросок на каждого,
       counter с 6 уходит тому же врагу.
  4. Раунд++.

Дракон: дыхание на turns_taken 0, 3, 6 (пока breaths_used < 3).
Шаман: каст пока MP > 0, потом посох со штрафом −1.
"""

import pytest

from burt.combat import (
    CombatState,
    EnemyInstance,
    BurtStats,
    RoundResult,
    start_combat,
    resolve_round,
)


# ─── Вспомогательное ───────────────────────────────────────

def rng_from(rolls):
    it = iter(rolls)

    def _rng():
        return next(it)

    return _rng


def make_burt(hp=10, hp_max=10, mp=0, mp_max=0,
              damage_min=1, damage_max=2,
              master=0, modifier=0):
    return BurtStats(
        hp=hp, hp_max=hp_max, mp=mp, mp_max=mp_max,
        damage_min=damage_min, damage_max=damage_max,
        master=master, modifier=modifier,
    )


# ─── Создание боя ──────────────────────────────────────────

class TestStartCombat:
    def test_burt_initiative(self):
        c = start_combat(["wolf"], "burt")
        assert c.initiative == "burt"
        assert c.round == 1
        assert c.active is True
        assert c.free_strike_done is True

    def test_enemy_initiative(self):
        c = start_combat(["wolf"], "enemy")
        assert c.initiative == "enemy"
        assert c.free_strike_done is False

    def test_ids_sequential_same_type(self):
        c = start_combat(["wolf", "wolf", "wolf"], "burt")
        assert [e.id for e in c.enemies] == ["wolf_1", "wolf_2", "wolf_3"]

    def test_ids_sequential_mixed_type(self):
        c = start_combat(["wolf", "goblin", "wolf"], "burt")
        assert [e.id for e in c.enemies] == ["wolf_1", "goblin_1", "wolf_2"]

    def test_hp_from_bestiary(self):
        c = start_combat(["wolf"], "burt")
        assert c.enemies[0].hp == 8
        assert c.enemies[0].hp_max == 8

    def test_shaman_mp(self):
        c = start_combat(["goblin_shaman"], "burt")
        assert c.enemies[0].mp == 5
        assert c.enemies[0].mp_max == 5

    def test_dragon_hp(self):
        c = start_combat(["dragon"], "burt")
        assert c.enemies[0].hp == 60

    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            start_combat([], "burt")

    def test_unknown_enemy_raises(self):
        with pytest.raises(ValueError):
            start_combat(["unicorn"], "burt")

    def test_invalid_initiative_raises(self):
        with pytest.raises(ValueError):
            start_combat(["wolf"], "self")


# ─── Сериализация ──────────────────────────────────────────

class TestSerialization:
    def test_roundtrip_basic(self):
        c = start_combat(["wolf", "wolf"], "burt")
        c.enemies[0].hp = 5
        c.enemies[1].hp = 3
        c2 = CombatState.from_dict(c.to_dict())
        assert c2.enemies[0].hp == 5
        assert c2.enemies[1].hp == 3
        assert c2.initiative == "burt"

    def test_roundtrip_shaman(self):
        c = start_combat(["goblin_shaman"], "enemy")
        c.enemies[0].mp = 2
        c2 = CombatState.from_dict(c.to_dict())
        assert c2.enemies[0].mp == 2

    def test_roundtrip_dragon(self):
        c = start_combat(["dragon"], "burt")
        c.enemies[0].turns_taken = 5
        c.enemies[0].breaths_used = 2
        c2 = CombatState.from_dict(c.to_dict())
        assert c2.enemies[0].turns_taken == 5
        assert c2.enemies[0].breaths_used == 2


# ─── Атака Бурта ───────────────────────────────────────────

class TestBurtAttack:
    def test_min_damage(self):
        # roll=3 → min 1. wolf 7. wolf отвечает roll=3 → min 1.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([3, 3]))
        assert r.combat.enemies[0].hp == 7

    def test_max_damage(self):
        # roll=5 → max 2. wolf 6.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([5, 3]))
        assert r.combat.enemies[0].hp == 6

    def test_critical_doubles_max(self):
        # roll=6 → max*2 = 4. wolf 4.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([6, 3]))
        assert r.combat.enemies[0].hp == 4

    def test_miss(self):
        # roll=2 → промах без штрафа. wolf 8.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([2, 3]))
        assert r.combat.enemies[0].hp == 8

    def test_crit_miss_self_penalty(self):
        # roll=1, master=0 → промах + −1 HP. burt 10-1-1=8.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([1, 3]))
        assert r.burt.hp == 8

    def test_kill(self):
        c = start_combat(["wolf"], "burt")
        c.enemies[0].hp = 1
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([3]))
        assert r.combat.enemies[0].alive is False
        assert r.outcome == "burt_won"

    def test_attack_dead_target_raises(self):
        c = start_combat(["wolf"], "burt")
        c.enemies[0].alive = False
        c.enemies[0].hp = 0
        burt = make_burt()
        with pytest.raises(ValueError):
            resolve_round(c, burt, "attack", "wolf_1", rng_from([3]))

    def test_attack_unknown_target_raises(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        with pytest.raises(ValueError):
            resolve_round(c, burt, "attack", "wolf_99", rng_from([3]))

    def test_target_required_for_attack(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        with pytest.raises(ValueError):
            resolve_round(c, burt, "attack", None, rng_from([3]))


# ─── Блок Бурта ────────────────────────────────────────────

class TestBurtBlock:
    def test_block_roll_5_no_damage(self):
        # block roll=5 → 0 входящего.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([5]))
        assert r.burt.hp == 10

    def test_block_roll_1_max_plus_penalty(self):
        # block roll=1 → max 3 + −1 HP = 4.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([1]))
        assert r.burt.hp == 6

    def test_block_roll_2_max_no_penalty(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([2]))
        assert r.burt.hp == 7

    def test_block_roll_3_avg(self):
        # wolf 1-3, avg = 2.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([3]))
        assert r.burt.hp == 8

    def test_block_roll_4_min(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([4]))
        assert r.burt.hp == 9

    def test_block_roll_6_counter(self):
        # block roll=6 → 0 incoming, counter avg=2. wolf 8-2=6.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([6]))
        assert r.burt.hp == 10
        assert r.combat.enemies[0].hp == 6

    def test_block_vs_two_wolves(self):
        c = start_combat(["wolf", "wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([5, 5]))
        assert r.burt.hp == 10

    def test_block_counter_hits_that_specific_enemy(self):
        # wolf_1: block roll=5 → 0. wolf_2: block roll=6 → counter 2.
        c = start_combat(["wolf", "wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "block", None, rng_from([5, 6]))
        assert r.combat.enemies[0].hp == 8
        assert r.combat.enemies[1].hp == 6


# ─── Побег ─────────────────────────────────────────────────

class TestBurtFlee:
    def test_flee_5_escapes_clean(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([5]))
        assert r.outcome == "burt_fled"
        assert r.burt.hp == 10

    def test_flee_1_fail_max(self):
        # flee roll=1 → провал + max входящий (3). burt 10→7.
        # wolf действует однократно: roll=3→min 1. burt 7→6.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([1, 3]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 6

    def test_flee_2_fail_min(self):
        # flee roll=2 → провал + min входящий (1). burt 10→9.
        # wolf действует: roll=2→miss (с узким пулом[1,3]: не узкий, roll=2 miss).
        # Итого uрон от wolves actions=0, HP остаётся 9.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([2, 2]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 9


# ─── Побег и ход врагов (кос. №4) ──────────────────────

class TestPostFleeEnemyTurn:
    """Кос. №4: при неудачном побеге враги получают ОДНО действие."""

    def test_flee_failed_wolf_melee(self):
        # Wolf действует после failed flee: roll=3→min 1. burt 10→7→6.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([2, 3]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 8  # 1(flee fail min) + 1(wolf melee)= 2 loss

    def test_flee_failed_shaman_casts(self):
        # Shaman с мана кастует после failed flee.
        # Roll=1 для flee: goblin_shaman damage=[0,1], roll=1 → incoming_max=1. HP 10→9.
        # Roll=3 для shaman spell: hit, dmg=3. HP 9→6.
        c = start_combat(["goblin_shaman"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([1, 3]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 6  # 1(flee max) + 3(spell hit)= 4 total loss
        assert r.combat.enemies[0].mp == 4  # потратил ману

    def test_flee_failed_shaman_no_mp_melee(self):
        # Шаман без маны бьёт посохом после failed flee.
        c = start_combat(["goblin_shaman"], "burt")
        c.enemies[0].mp = 0  # нет маны → мили
        burt = make_burt()
        # flee roll=2→fail+min(0)=0. HP остаётся 10.
        # Staff: staff_penalty=-1, roll=3→eff 2→miss. HP=10.
        r = resolve_round(c, burt, "flee", None, rng_from([2, 3]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 10  # 0(flee fail min) + 0(staff miss)

    def test_flee_multiple_enemies_all_act(self):
        # Два врага: каждый действует однократно.
        # wolf1: flee roll=2→fail+min1. HP 10→9.
        # wolf1 turn: roll=3→min 1. HP 9→8.
        # wolf2 turn: roll=4→avg 2. HP 8→6.
        c = start_combat(["wolf", "wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([2, 3, 4]))
        assert r.outcome == "ongoing"
        assert r.burt.hp == 6  # 1 + 1 + 2 = 4 total damage



    def test_flee_3_with_hit(self):
        # flee roll=3, hit_roll=4 → ушёл, получил min 1.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([3, 4]))
        assert r.outcome == "burt_fled"
        assert r.burt.hp == 9

    def test_flee_3_no_hit(self):
        # flee roll=3, hit_roll=3 → ушёл без урона.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([3, 3]))
        assert r.outcome == "burt_fled"
        assert r.burt.hp == 10

    def test_flee_6_counter(self):
        # flee roll=6 → ушёл + counter min 1. wolf 7.
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "flee", None, rng_from([6]))
        assert r.outcome == "burt_fled"
        assert r.combat.enemies[0].hp == 7

    def test_flee_from_dragon_raises(self):
        c = start_combat(["dragon"], "burt")
        burt = make_burt()
        with pytest.raises(ValueError):
            resolve_round(c, burt, "flee", None, rng_from([5]))


# ─── Free strike ───────────────────────────────────────────

class TestFreeStrike:
    def test_free_strike_then_burt_acts(self):
        # rng=[5, 3, 3]
        # free: goblin roll=5 → max 2. burt 10→8.
        # burt attack: roll=3 → min 1. goblin 6→5.
        # goblin turn: roll=3 → min 1. burt 8→7.
        c = start_combat(["goblin"], "enemy")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "goblin_1", rng_from([5, 3, 3]))
        assert r.burt.hp == 7
        assert r.combat.enemies[0].hp == 5
        assert r.combat.free_strike_done is True

    def test_free_strike_kills_burt(self):
        # free: wolf roll=5 → max 3. burt 2 → −1.
        c = start_combat(["wolf"], "enemy")
        burt = make_burt(hp=2)
        r = resolve_round(c, burt, "block", None, rng_from([5]))
        assert r.outcome == "burt_died"

    def test_no_free_strike_when_burt_first(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        # rng=[3, 3] — 2 броска, не 3.
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([3, 3]))
        assert r.burt.hp == 9
        assert r.combat.free_strike_done is True

    def test_free_strike_only_once(self):
        c = start_combat(["wolf"], "enemy")
        burt = make_burt()
        r1 = resolve_round(c, burt, "attack", "wolf_1", rng_from([5, 3, 3]))
        # round 2: без free strike, 2 броска.
        r2 = resolve_round(r1.combat, r1.burt, "attack", "wolf_1",
                           rng_from([3, 3]))
        # r1: burt 10−3−1=6. r2: −1 → 5.
        assert r2.burt.hp == 5


# ─── Шаман ─────────────────────────────────────────────────

class TestShaman:
    def test_shaman_casts_spell(self):
        # rng=[3, 3]
        # burt attack: roll=3 → 1. shaman hp 8→7.
        # shaman spell: roll=3 → min 3. burt 20→17. mp 5→4.
        c = start_combat(["goblin_shaman"], "burt")
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 3]),
        )
        assert r.burt.hp == 17
        assert r.combat.enemies[0].mp == 4

    def test_shaman_staff_after_mp(self):
        # mp=0 → посох, штраф −1. roll=3 → eff 2 → промах.
        c = start_combat(["goblin_shaman"], "burt")
        c.enemies[0].mp = 0
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 3]),
        )
        assert r.burt.hp == 20

    def test_shaman_staff_never_crits(self):
        # roll=6, modifier −1 → eff 5 → max 1. Не крит.
        c = start_combat(["goblin_shaman"], "burt")
        c.enemies[0].mp = 0
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 6]),
        )
        assert r.burt.hp == 19


# ─── Заклинание врага с блоком (кос. №2) ──────────────────

class TestEnemySpellVsBlock:
    """Кос. №2: всегда бросаем кубик атаки даже при касте.

    В текущей архитектуре «блок» не передаёт block_roll
    в _enemy_spell/_enemy_melee (см. resolve_round). Поэтому
    блок семантический, не механический. Код _enemy_spell стал
    правильным на случай если архитектуру расширят.

    Гоблин-шаман: spell_damage_min=3, spell_damage_max=6.
    Resolve attack roll=3 на [3..6] → min damage = 3.
    """

    def test_enemy_spell_no_block_hit(self):
        # Шаман кастует, атака попала (roll=3→min=3).
        c = start_combat(["goblin_shaman"], "burt")
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 3]),
        )
        assert r.burt.hp == 17  # 3 урона от spell
        assert r.combat.enemies[0].mp == 4

    def test_enemy_spell_no_block_miss(self):
        # Шаман кастует, атака промахнулась (roll=1→miss).
        c = start_combat(["goblin_shaman"], "burt")
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 1]),
        )
        assert r.burt.hp == 20  # 0 урона: атака промахнулась
        assert r.combat.enemies[0].mp == 4  # ману потратил

    def test_enemy_spell_mp_spent_on_miss(self):
        # Ману тратим даже когда каст промахивается.
        c = start_combat(["goblin_shaman"], "burt")
        c.enemies[0].mp = 5
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 1]),
        )
        assert r.combat.enemies[0].mp == 4  # потратил spite miss

    def test_enemy_spell_mp_spent_on_hit(self):
        # Ману тратим когда каст попал тоже.
        c = start_combat(["goblin_shaman"], "burt")
        c.enemies[0].mp = 5
        burt = make_burt(hp=20, hp_max=20)
        r = resolve_round(
            c, burt, "attack", "goblin_shaman_1", rng_from([3, 3]),
        )
        assert r.combat.enemies[0].mp == 4  # потратил spite hit



# ─── Дракон ────────────────────────────────────────────────

class TestDragon:
    def test_breath_first_turn(self):
        # turns_taken=0 → дыхание. roll=3 → min 12. burt 50→38.
        c = start_combat(["dragon"], "burt")
        burt = make_burt(hp=50, hp_max=50)
        r = resolve_round(c, burt, "attack", "dragon_1", rng_from([3, 3]))
        assert r.burt.hp == 38
        assert r.combat.enemies[0].breaths_used == 1

    def test_bite_second_turn(self):
        # turns_taken=1 → клыки. roll=3 → min 16. burt 50→34.
        c = start_combat(["dragon"], "burt")
        c.enemies[0].turns_taken = 1
        c.enemies[0].breaths_used = 1
        burt = make_burt(hp=50, hp_max=50)
        r = resolve_round(c, burt, "attack", "dragon_1", rng_from([3, 3]))
        assert r.burt.hp == 34
        assert r.combat.enemies[0].breaths_used == 1

    def test_breath_fourth_turn(self):
        # turns_taken=3 → дыхание. burt 50→38.
        c = start_combat(["dragon"], "burt")
        c.enemies[0].turns_taken = 3
        c.enemies[0].breaths_used = 1
        burt = make_burt(hp=50, hp_max=50)
        r = resolve_round(c, burt, "attack", "dragon_1", rng_from([3, 3]))
        assert r.burt.hp == 38
        assert r.combat.enemies[0].breaths_used == 2

    def test_no_more_than_3_breaths(self):
        # breaths_used=3 → больше не дышит. Клыки, min 16.
        c = start_combat(["dragon"], "burt")
        c.enemies[0].turns_taken = 9
        c.enemies[0].breaths_used = 3
        burt = make_burt(hp=100, hp_max=100)
        r = resolve_round(c, burt, "attack", "dragon_1", rng_from([3, 3]))
        assert r.burt.hp == 84
        assert r.combat.enemies[0].breaths_used == 3


# ─── Конец боя ─────────────────────────────────────────────

class TestEndConditions:
    def test_burt_died_from_enemy(self):
        # burt attack: roll=3 → 1. wolf 7.
        # wolf: roll=5 → max 3. burt 1−3=−2.
        c = start_combat(["wolf"], "burt")
        burt = make_burt(hp=1)
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([3, 5]))
        assert r.outcome == "burt_died"

    def test_burt_died_from_self_penalty(self):
        # roll=1 → промах + −1 HP. burt 1→0.
        c = start_combat(["wolf"], "burt")
        burt = make_burt(hp=1)
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([1]))
        assert r.outcome == "burt_died"

    def test_ongoing_round_increments(self):
        c = start_combat(["wolf"], "burt")
        burt = make_burt()
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([3, 3]))
        assert r.outcome == "ongoing"
        assert r.combat.active is True
        assert r.combat.round == 2

    def test_kill_one_of_two(self):
        c = start_combat(["wolf", "wolf"], "burt")
        c.enemies[0].hp = 1
        burt = make_burt()
        # rng=[5, 3]: burt roll=5 → 2 dmg. wolf_1 dead.
        # wolf_2: roll=3 → min 1. burt 9.
        r = resolve_round(c, burt, "attack", "wolf_1", rng_from([5, 3]))
        assert r.combat.enemies[0].alive is False
        assert r.combat.enemies[1].alive is True
        assert r.burt.hp == 9