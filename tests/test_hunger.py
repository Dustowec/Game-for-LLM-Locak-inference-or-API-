"""
Тесты для burt/hunger.py — §4 ТЗ v0.7.0.

Hunger: жёсткий порог, не шкала.
Инжект «ты hungry» — строго по флагу eat: голоден -> инжект, сыт -> тишина.
Смерть на 8 и 18 при eat=False.
Рес: 1d6, 6 = жив, 2 HP. Не чаще 1 раза в day.
Если рес использован — окончательная смерть без броска.

Проверка — на выходе из хода (после действия модели).

BUG FIX (HANDOFF-11.1): раньше на шагах 0 и 10 был "обязательный" инжект
вне зависимости от eat. Это создавало противоречие: [STATE] Hunger: full,
а инжект "You are hungry". Модель сбивалась и ела хлеб, будучи сытой.
Теперь инжект зависит ТОЛЬКО от eat.
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
        # Legacy: константа сохранена для совместимости,
        # но на инжект больше не влияет.
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
    Инжект «ты hungry» в сенсорный отчёт.

    Инвариант: eat=True -> никогда; eat=False -> всегда.
    Шаг не влияет (см. bug fix HANDOFF-11.1).
    """

    # ── Сыт (eat=True) -> НИКОГДА не инжектим, на любом шаге ──

    @pytest.mark.parametrize("step", range(20))
    def test_never_injects_when_fed(self, step):
        assert should_inject_hunger(step, eat=True) is False

    # ── Голоден (eat=False) -> ВСЕГДА инжектим, на любом шаге ──

    @pytest.mark.parametrize("step", range(20))
    def test_always_injects_when_hungry(self, step):
        assert should_inject_hunger(step, eat=False) is True

    # ── Именованные кейсы на границах циклов (0, 10) для читаемости ──
    # Раньше здесь ожидался True даже при eat=True (boundary inject).
    # Bug fix: теперь False — согласовано с [STATE] Hunger: full.

    def test_step_0_injects_when_hungry(self):
        assert should_inject_hunger(0, eat=False) is True

    def test_step_0_silent_when_fed(self):
        # Bug fix: было True (boundary inject), стало False.
        assert should_inject_hunger(0, eat=True) is False

    def test_step_10_injects_when_hungry(self):
        assert should_inject_hunger(10, eat=False) is True

    def test_step_10_silent_when_fed(self):
        # Bug fix: было True (boundary inject), стало False.
        assert should_inject_hunger(10, eat=True) is False


# ─── resolve_hunger ────────────────────────────────────────

class TestResolveHunger:
    """
    Проверка голода на ВЫХОДЕ из хода.

    Вызывается после того, как модель выбрала и исполнила действие.
    roll — значение 1d6, бросается вызывающей стороной только когда нужно
    (или передаётся всегда, но игнорируется в безопасных случаях).
    """

    @pytest.mark.parametrize("step", [0, 1, 5, 7, 9, 10, 15, 17, 19])
    def test_no_death_on_safe_step_hungry(self, step):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=1,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [0, 1, 5, 7, 9, 10, 15, 17, 19])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_no_death_on_safe_step_any_roll(self, step, roll):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [8, 18])
    def test_no_death_if_fed(self, step):
        result = resolve_hunger(
            step, eat=True, resurrection_used_today=False, roll=1,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 3, 5, 6])
    def test_no_death_if_fed_any_roll(self, step, roll):
        result = resolve_hunger(
            step, eat=True, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.NO_DEATH

    @pytest.mark.parametrize("step", [8, 18])
    def test_resurrection_on_roll_6(self, step):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=6,
        )
        assert result == HungerOutcome.RESURRECTED

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5])
    def test_final_death_on_roll_not_6(self, step, roll):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=False, roll=roll,
        )
        assert result == HungerOutcome.FINAL_DEATH

    @pytest.mark.parametrize("step", [8, 18])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_final_death_if_resurrection_used(self, step, roll):
        result = resolve_hunger(
            step, eat=False, resurrection_used_today=True, roll=roll,
        )
        assert result == HungerOutcome.FINAL_DEATH

    def test_used_resurrection_blocks_second_miracle(self):
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
        eat, hp = apply_eat(eat=True, hp=5, hp_max=10)
        assert eat is True
        assert hp == 6


# ─── reset_hunger_after_sleep ──────────────────────────────

class TestResetHungerAfterSleep:
    """
    После сна: eat=False (просыпается голодным, шаг 0),
    флаг реса сбрасывается (новый day = новая милость).
    """

    def test_sleep_resets_eat(self):
        eat, _ = reset_hunger_after_sleep()
        assert eat is False

    def test_sleep_resets_resurrection_flag(self):
        _, res_used = reset_hunger_after_sleep()
        assert res_used is False