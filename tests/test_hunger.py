"""
Тесты для burt/hunger.py — §4 ТЗ v0.7.0.

Голод: жёсткий порог, не шкала.
Инжект на 0 и 10 — обязательный.
Инжект на 1-9 и 11-19 — при eat=False.
Смерть на 8 и 18 при eat=False.
Рес: 1d6, 6 = жив, 2 HP. Не чаще 1 раза в день.
Если рес использован — окончательная смерть без броска.

Проверка — на выходе из хода (после действия модели).
"""

import pytest

from burt.hunger import (
    HUNGER_HUNGRY_AT,
    HUNGER_DEATH_AT,
    RESURRECTION_HP,
    FOOD_HEAL,
    HungerOutcome,
    should_inject_hunger,
    resolve_hunger,
    apply_eat,
    reset_hunger_after_sleep,
)


# ─── Константы ─────────────────────────────────────────────

class TestConstants:
    def test_hungry_at(self):
        assert HUNGER_HUNGRY_AT == (0, 10)

    def test_death_at(self):
        assert HUNGER_DEATH_AT == (8, 18)

    def test_resurrection_hp(self):
        assert RESURRECTION_HP == 2

    def test_food_heal(self):
        assert FOOD_HEAL == 1


# ─── should_inject_hunger ──────────────────────────────────

class TestShouldInjectHunger:
    """
    Инжект «ты голоден» в сенсорный отчёт.

    Шаги 0 и 10 — обязательный инжект, вне зависимости от eat.
    Шаги 1-9, 11-19 — инжект только при eat=False.
    """

    # Обязательные шаги: 0 и 10.

    def test_step_0_injects_when_hungry(self):
        assert should_inject_hunger(0, eat=False) is True

    def test_step_0_injects_when_fed(self):
        # Обязательный инжект. Если модель как-то оказалась сытой на шаге 0 —
        # это аномалия, но инжект по спеке всё равно должен быть.
        assert should_inject_hunger(0, eat=True) is True

    def test_step_10_injects_when_hungry(self):
        assert should_inject_hunger(10, eat=False) is True

    def test_step_10_injects_when_fed(self):
        # Новый цикл. Безусловный инжект.
        assert should_inject_hunger(10, eat=True) is True

    # Шаги 1-9: при eat=False — инжект каждый ход.

    @pytest.mark.parametrize("step", [1, 2, 3, 4, 5, 6, 7, 8, 9])
    def test_steps_1_to_9_inject_when_hungry(self, step):
        assert should_inject_hunger(step, eat=False) is True

    # Шаги 1-7: при eat=True — инжект снят (явно в ТЗ).

    @pytest.mark.parametrize("step", [1, 2, 3, 4, 5, 6, 7])
    def test_steps_1_to_7_silent_when_fed(self, step):
        assert should_inject_hunger(step, eat=True) is False

    # Шаги 8, 9: при eat=True — инжект снят.
    # ПРЕДПОЛОЖЕНИЕ: ТЗ явно перечисляет 1-7, но симметрия требует,
    # что при eat=True модель не голодна и на 8, 9.
    # На 8 при eat=False инжект обязателен: иначе модель не узнает,
    # что надо поесть, чтобы не умереть на выходе из хода.

    @pytest.mark.parametrize("step", [8, 9])
    def test_steps_8_9_silent_when_fed(self, step):
        assert should_inject_hunger(step, eat=True) is False

    # Шаги 11-19: при eat=False — инжект каждый ход.

    @pytest.mark.parametrize("step", [11, 12, 13, 14, 15, 16, 17, 18, 19])
    def test_steps_11_to_19_inject_when_hungry(self, step):
        assert should_inject_hunger(step, eat=False) is True

    # Шаги 11-17: при eat=True — инжект снят (явно в ТЗ).

    @pytest.mark.parametrize("step", [11, 12, 13, 14, 15, 16, 17])
    def test_steps_11_to_17_silent_when_fed(self, step):
        assert should_inject_hunger(step, eat=True) is False

    # Шаги 18, 19: при eat=True — инжект снят.
    # ПРЕДПОЛОЖЕНИЕ: симметрично 8, 9.

    @pytest.mark.parametrize("step", [18, 19])
    def test_steps_18_19_silent_when_fed(self, step):
        assert should_inject_hunger(step, eat=True) is False


# ─── resolve_hunger ────────────────────────────────────────

class TestResolveHunger:
    """
    Проверка голода на ВЫХОДЕ из хода.

    Вызывается после того, как модель выбрала и исполнила действие.
    roll — значение 1d6, бросается вызывающей стороной только когда нужно
    (или передаётся всегда, но игнорируется в безопасных случаях).
    """

    # Не на шаге смерти — NO_DEATH, вне зависимости от eat и roll.

    @pytest.mark.parametrize("step", [0, 1, 5, 7, 9, 10, 15, 17, 19])
    def test_no_death_on_safe_step_hungry(self, step):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=1,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [0, 1, 5, 7, 9, 10, 15, 17, 19])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_no_death_on_safe_step_any_roll(self, step, roll):
        # На безопасном шаге кубик вообще не должен влиять.
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.NO_DEATH

    # Шаг смерти, но поела — NO_DEATH.

    @pytest.mark.parametrize("step", [8, 18])
    def test_no_death_if_fed(self, step):
        result = resolve_hunger(
            step, eat=True, resurrection_used_today=False, roll=1,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 3, 5, 6])
    def test_no_death_if_fed_any_roll(self, step, roll):
        # Даже если кубик выпал 6 — при eat=True смерти нет.
        result = resolve_hunger(
            step, eat=True, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.NO_DEATH

    # Шаг смерти, не поела, рес не использован, кубик = 6 → RESURRECTED.

    @pytest.mark.parametrize("step", [8, 18])
    def test_resurrection_on_roll_6(self, step):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=6,
        )
        assert result == HungerOutcome.RESURRECTED

    # Шаг смерти, не поела, рес не использован, кубик != 6 → FINAL_DEATH.

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5])
    def test_final_death_on_roll_not_6(self, step, roll):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.FINAL_DEATH

    # Шаг смерти, не поела, рес уже использован сегодня → FINAL_DEATH
    # независимо от кубика (в т.ч. при roll=6 — второй милости нет).

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_final_death_if_resurrection_used(self, step, roll):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=True, roll=roll,
        )
        assert result == HungerOutcome.FINAL_DEATH

    def test_used_resurrection_blocks_second_miracle(self):
        # Акцентируем: если рес уже был сегодня — кубик не спасает.
        for step in HUNGER_DEATH_AT:
            assert resolve_hunger(
                step, eat=False, resurrection_used_today=True, roll=6,
            ) == HungerOutcome.FINAL_DEATH


# ─── apply_eat ─────────────────────────────────────────────

class TestApplyEat:
    """
    Еда: снимает голод (eat=True), восстанавливает +1 HP.
    MP не восстанавливает.
    """

    def test_eat_when_hungry_and_wounded(self):
        eat, hp = apply_eat(eat=False, hp=5, hp_max=10)
        assert eat is True
        assert hp == 6

    def test_eat_restores_exactly_one_hp(self):
        _, hp = apply_eat(eat=False, hp=3, hp_max=10)
        assert hp == 4

    def test_eat_does_not_exceed_max_hp(self):
        _, hp = apply_eat(eat=False, hp=9, hp_max=10)
        assert hp == 10

    def test_eat_at_full_hp_stays_at_max(self):
        eat, hp = apply_eat(eat=False, hp=10, hp_max=10)
        assert eat is True
        assert hp == 10

    def test_repeat_eat_still_heals(self):
        # Повторная еда в том же цикле — eat уже True, но +1 HP всё равно.
        eat, hp = apply_eat(eat=True, hp=5, hp_max=10)
        assert eat is True
        assert hp == 6


# ─── reset_hunger_after_sleep ──────────────────────────────

class TestResetHungerAfterSleep:
    """
    После сна: eat=False (просыпается голодным, шаг 0),
    флаг реса сбрасывается (новый день = новая милость).
    """

    def test_sleep_resets_eat(self):
        eat, _ = reset_hunger_after_sleep()
        assert eat is False

    def test_sleep_resets_resurrection_flag(self):
        _, res_used = reset_hunger_after_sleep()
        assert res_used is False