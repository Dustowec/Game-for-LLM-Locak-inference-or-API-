"""Тесты для burt.dice — кубик и таблицы §10 ТЗ v0.7.0.

TDD: сначала спецификация поведения, потом имплементация.
Все функции принимают roll явно — никакого рандома в тестах.
"""

import pytest

from burt.dice import (
    roll_d6,
    resolve_attack,
    resolve_block,
    resolve_dialog,
    resolve_dialog_second_roll,
    resolve_movement,
    resolve_search,
    resolve_craft,
    resolve_random_event,
    resolve_flee,
)


# ---------------------------------------------------------------------
# roll_d6
# ---------------------------------------------------------------------

def test_roll_d6_in_range():
    for _ in range(1000):
        assert 1 <= roll_d6() <= 6


def test_roll_d6_distribution_roughly_uniform():
    counts = {i: 0 for i in range(1, 7)}
    for _ in range(6000):
        counts[roll_d6()] += 1
    for v in counts.values():
        # ~1000 на грань, допускаем 30% отклонения
        assert 700 <= v <= 1300


# ---------------------------------------------------------------------
# resolve_attack — таблица атаки §10
# 1 — промах + штраф −1 HP
# 2 — промах
# 3 — минимальный урон
# 4 — средний урон
# 5 — максимальный урон
# 6 — урон ×2
# ---------------------------------------------------------------------

def test_attack_roll1_crit_miss_with_penalty():
    r = resolve_attack(roll=1, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is False
    assert r.damage == 0
    assert r.self_penalty_hp == 1


def test_attack_roll2_miss_no_penalty():
    r = resolve_attack(roll=2, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is False
    assert r.damage == 0
    assert r.self_penalty_hp == 0


def test_attack_roll3_min_damage():
    r = resolve_attack(roll=3, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is True
    assert r.damage == 2


def test_attack_roll4_avg_damage_floor():
    # меч 2-4: avg = (2+4)//2 = 3
    r = resolve_attack(roll=4, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is True
    assert r.damage == 3


def test_attack_roll5_max_damage():
    r = resolve_attack(roll=5, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is True
    assert r.damage == 4


def test_attack_roll6_double_max():
    r = resolve_attack(roll=6, damage_min=2, damage_max=4, master=0, modifier=0)
    assert r.hit is True
    assert r.damage == 8  # 2 * max


def test_attack_narrow_pool_dublina_1_2():
    # дубина 1-2: диапазон <3 клеток -> средний = минимальный
    # 3 -> min, 4 -> min, 5 -> max, 6 -> 2*max
    assert resolve_attack(3, 1, 2).damage == 1
    assert resolve_attack(4, 1, 2).damage == 1
    assert resolve_attack(5, 1, 2).damage == 2
    assert resolve_attack(6, 1, 2).damage == 4


def test_attack_narrow_pool_fists_0_1():
    # кулаки 0-1: диапазон <3 клеток
    assert resolve_attack(3, 0, 1).damage == 0
    assert resolve_attack(4, 0, 1).damage == 0
    assert resolve_attack(5, 0, 1).damage == 1
    assert resolve_attack(6, 0, 1).damage == 2


def test_attack_master5_no_crit_miss():
    # порог 5: крит-промах исчезает
    r = resolve_attack(roll=1, damage_min=2, damage_max=4, master=5, modifier=0)
    assert r.hit is False
    assert r.damage == 0
    assert r.self_penalty_hp == 0


def test_attack_master5_still_misses_on_2():
    r = resolve_attack(roll=2, damage_min=2, damage_max=4, master=5, modifier=0)
    assert r.hit is False
    assert r.damage == 0
    assert r.self_penalty_hp == 0


def test_attack_master10_no_misses():
    # порог 10: промахов нет, 1 и 2 дают минимальный урон
    for roll in (1, 2):
        r = resolve_attack(roll=roll, damage_min=2, damage_max=4, master=10, modifier=0)
        assert r.hit is True
        assert r.damage == 2


def test_attack_modifier_shifts_roll_up():
    # +1 к броску: roll 2 -> effective 3 -> мин урон
    r = resolve_attack(roll=2, damage_min=2, damage_max=4, master=0, modifier=+1)
    assert r.hit is True
    assert r.damage == 2


def test_attack_modifier_shifts_roll_down():
    # -1 к броску: roll 5 -> effective 4 -> средний урон
    r = resolve_attack(roll=5, damage_min=2, damage_max=4, master=0, modifier=-1)
    assert r.hit is True
    assert r.damage == 3


def test_attack_modifier_clamps_at_1():
    # roll 1 с -1: effective не ниже 1 -> крит-промах
    r = resolve_attack(roll=1, damage_min=2, damage_max=4, master=0, modifier=-1)
    assert r.hit is False
    assert r.self_penalty_hp == 1


def test_attack_modifier_clamps_at_6():
    # roll 6 с +1: effective не выше 6 -> двойной урон
    r = resolve_attack(roll=6, damage_min=2, damage_max=4, master=0, modifier=+1)
    assert r.hit is True
    assert r.damage == 8


# ---------------------------------------------------------------------
# resolve_block — таблица блока/уклонения §10
# 1 — провал + макс входящий + −1 HP
# 2 — провал + макс входящий
# 3 — входящий средний
# 4 — входящий минимальный
# 5 — входящий ноль
# 6 — ноль + ответный средний (бесплатно)
# ---------------------------------------------------------------------

def test_block_roll1_crit_fail():
    r = resolve_block(roll=1, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 3
    assert r.self_penalty_hp == 1
    assert r.counter_damage == 0


def test_block_roll2_fail_max_incoming():
    r = resolve_block(roll=2, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 3
    assert r.self_penalty_hp == 0


def test_block_roll3_avg_incoming():
    r = resolve_block(roll=3, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 2


def test_block_roll4_min_incoming():
    r = resolve_block(roll=4, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 1


def test_block_roll5_zero_incoming():
    r = resolve_block(roll=5, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 0
    assert r.counter_damage == 0


def test_block_roll6_counter_avg():
    r = resolve_block(roll=6, incoming_min=1, incoming_max=3,
                      counter_min=2, counter_max=4)
    assert r.incoming_damage == 0
    assert r.counter_damage == 3  # avg 2-4


# ---------------------------------------------------------------------
# resolve_dialog — пары §12
# 1-2 — провал, 3-4 — нейтрал, 5-6 — успех
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll,expected", [
    (1, "fail"),
    (2, "fail"),
    (3, "neutral"),
    (4, "neutral"),
    (5, "success"),
    (6, "success"),
])
def test_dialog_pairs(roll, expected):
    assert resolve_dialog(roll).result == expected


def test_dialog_modifier_shifts_pairs():
    # +1: 4 -> 5 -> успех
    assert resolve_dialog(4, modifier=+1).result == "success"
    # -1: 3 -> 2 -> провал
    assert resolve_dialog(3, modifier=-1).result == "fail"


# ---------------------------------------------------------------------
# resolve_dialog_second_roll — второй бросок §12
# fail: 1-3 -> -1 HP + ярость, 4-6 -> просто отказ
# success: 1-3 -> бонус, 4-6 -> без бонуса
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll", [1, 2, 3])
def test_dialog_fail_second_roll_penalty_and_angry(roll):
    r = resolve_dialog_second_roll(roll, kind="fail")
    assert r.penalty_hp is True
    assert r.angry is True


@pytest.mark.parametrize("roll", [4, 5, 6])
def test_dialog_fail_second_roll_no_penalty(roll):
    r = resolve_dialog_second_roll(roll, kind="fail")
    assert r.penalty_hp is False
    assert r.angry is False


@pytest.mark.parametrize("roll", [1, 2, 3])
def test_dialog_success_second_roll_bonus(roll):
    r = resolve_dialog_second_roll(roll, kind="success")
    assert r.bonus is True


@pytest.mark.parametrize("roll", [4, 5, 6])
def test_dialog_success_second_roll_no_bonus(roll):
    r = resolve_dialog_second_roll(roll, kind="success")
    assert r.bonus is False


def test_dialog_second_roll_invalid_kind():
    with pytest.raises(ValueError):
        resolve_dialog_second_roll(3, kind="neutral")


# ---------------------------------------------------------------------
# resolve_movement — §10
# 1 — провал + плохое, 2 — провал, 3-4 — норма, 5 — хорошо,
# 6 — отлично + хорошее
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll,expected", [
    (1, "fail_bad"),
    (2, "fail"),
    (3, "normal"),
    (4, "normal"),
    (5, "good"),
    (6, "great"),
])
def test_movement(roll, expected):
    assert resolve_movement(roll).result == expected


# ---------------------------------------------------------------------
# resolve_search — §14
# 1 — провал+штраф, 2 — неудача, 3-4 — частичный,
# 5 — успех, 6 — крит
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll,expected", [
    (1, "fail_penalty"),
    (2, "fail"),
    (3, "partial"),
    (4, "partial"),
    (5, "success"),
    (6, "crit"),
])
def test_search(roll, expected):
    assert resolve_search(roll).result == expected


# ---------------------------------------------------------------------
# resolve_craft — §10
# 1-2 — провал, 3-4 — успех, 5-6 — полный успех + бонус
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll,expected", [
    (1, "fail"),
    (2, "fail"),
    (3, "success"),
    (4, "success"),
    (5, "perfect"),
    (6, "perfect"),
])
def test_craft(roll, expected):
    assert resolve_craft(roll).result == expected


# ---------------------------------------------------------------------
# resolve_random_event — §10
# 1-2 — плохое, 3-4 — ничего, 5-6 — хорошее
# ---------------------------------------------------------------------

@pytest.mark.parametrize("roll,expected", [
    (1, "bad"),
    (2, "bad"),
    (3, "nothing"),
    (4, "nothing"),
    (5, "good"),
    (6, "good"),
])
def test_random_event(roll, expected):
    assert resolve_random_event(roll).result == expected


# ---------------------------------------------------------------------
# resolve_flee — §23
# 1 — провал + враг бьёт бесплатно макс
# 2 — провал + враг бьёт бесплатно мин
# 3-4 — ушёл (но враг может ударить, если hit_roll >= 4)
# 5 — ушёл
# 6 — ушёл + нанёс врагу мин
# ---------------------------------------------------------------------

def test_flee_roll1_fail_takes_max():
    r = resolve_flee(roll=1, incoming_min=2, incoming_max=5)
    assert r.escaped is False
    assert r.incoming_damage == 5


def test_flee_roll2_fail_takes_min():
    r = resolve_flee(roll=2, incoming_min=2, incoming_max=5)
    assert r.escaped is False
    assert r.incoming_damage == 2


def test_flee_roll34_escaped_with_hit_roll_ge_4():
    # 3-4: ушёл, но враг может ударить при hit_roll >= 4
    r = resolve_flee(roll=3, incoming_min=2, incoming_max=5, hit_roll=4)
    assert r.escaped is True
    assert r.incoming_damage == 2


def test_flee_roll34_escaped_with_hit_roll_lt_4():
    r = resolve_flee(roll=3, incoming_min=2, incoming_max=5, hit_roll=3)
    assert r.escaped is True
    assert r.incoming_damage == 0


def test_flee_roll34_requires_hit_roll():
    with pytest.raises(ValueError):
        resolve_flee(roll=3, incoming_min=2, incoming_max=5)


def test_flee_roll5_escaped_clean():
    r = resolve_flee(roll=5, incoming_min=2, incoming_max=5)
    assert r.escaped is True
    assert r.incoming_damage == 0
    assert r.counter_damage == 0


def test_flee_roll6_escaped_and_counter_min():
    r = resolve_flee(roll=6, incoming_min=2, incoming_max=5,
                     counter_min=1, counter_max=3)
    assert r.escaped is True
    assert r.incoming_damage == 0
    assert r.counter_damage == 1


# ---------------------------------------------------------------------
# Граничные проверки на входные данные
# ---------------------------------------------------------------------

def test_attack_rejects_invalid_roll():
    with pytest.raises(ValueError):
        resolve_attack(roll=0, damage_min=1, damage_max=2)


def test_attack_rejects_damage_min_gt_max():
    with pytest.raises(ValueError):
        resolve_attack(roll=3, damage_min=5, damage_max=2)


def test_block_rejects_invalid_roll():
    with pytest.raises(ValueError):
        resolve_block(roll=7, incoming_min=1, incoming_max=3)