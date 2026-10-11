"""
Тесты для burt/sleep.py — §5 ТЗ v0.7.0.

Сон:
  - доступен с шага 19, только при (спальный мешок ИЛИ комната) и вне боя;
  - на шаге 20, если модель не выбрала сон — принудительный;
  - сон = новый день: wrap → step 0, day+1 (независимо от того, на 19 или 20);
  - при любом сне: HP/MP = max, эффекты сняты;
  - дневник: выбрала спать → пишет Бурт, иначе → пишет МИР.

Чистое ядро: без I/O, без asyncio, без LLM.
"""

import pytest

from burt.sleep import (
    TIRED_AT,
    SLEEP_AVAILABLE_FROM,
    SLEEP_FORCED_AT,
    DIARY_SOURCE_BURT,
    DIARY_SOURCE_WORLD,
    should_inject_tired,
    is_sleep_available,
    is_forced_sleep,
    diary_source,
    apply_sleep,
)


# ─── Константы ─────────────────────────────────────────────

class TestConstants:
    def test_tired_at(self):
        assert TIRED_AT == (19, 20)

    def test_sleep_available_from(self):
        assert SLEEP_AVAILABLE_FROM == 19

    def test_sleep_forced_at(self):
        assert SLEEP_FORCED_AT == 20

    def test_diary_sources(self):
        assert DIARY_SOURCE_BURT == "burt"
        assert DIARY_SOURCE_WORLD == "world"


# ─── should_inject_tired ───────────────────────────────────

class TestShouldInjectTired:
    """Инжект «ты устал» / «ты сильно устал» на входе в шаг."""

    def test_step_19_injects(self):
        assert should_inject_tired(19) is True

    def test_step_20_injects(self):
        assert should_inject_tired(20) is True

    @pytest.mark.parametrize("step", [0, 1, 5, 10, 15, 18, 21])
    def test_other_steps_no_inject(self, step):
        assert should_inject_tired(step) is False


# ─── is_sleep_available ────────────────────────────────────

class TestIsSleepAvailable:
    """
    Сон доступен, если:
      - не в бою;
      - шаг >= 19;
      - есть спальный мешок ИЛИ куплена комната.
    """

    # Базовый случай: всё есть.

    def test_step_19_with_bedroll(self):
        assert is_sleep_available(19, False, True, False) is True

    def test_step_19_with_room(self):
        assert is_sleep_available(19, False, False, True) is True

    def test_step_20_with_bedroll(self):
        assert is_sleep_available(20, False, True, False) is True

    def test_step_20_with_room(self):
        assert is_sleep_available(20, False, False, True) is True

    # До 19 — недоступно, даже если всё есть.

    @pytest.mark.parametrize("step", [0, 1, 5, 10, 15, 18])
    def test_before_19_unavailable(self, step):
        assert is_sleep_available(step, False, True, True) is False

    # В бою — недоступно, даже на 19/20.

    @pytest.mark.parametrize("step", [19, 20])
    def test_in_combat_unavailable(self, step):
        assert is_sleep_available(step, True, True, True) is False

    # Нет ни мешка, ни комнаты — недоступно.

    @pytest.mark.parametrize("step", [19, 20])
    def test_no_condition_unavailable(self, step):
        assert is_sleep_available(step, False, False, False) is False


# ─── is_forced_sleep ───────────────────────────────────────

class TestIsForcedSleep:
    """
    Принудительный сон = шаг 20 и модель не выбрала сон.

    На шаге 19 сон — только добровольный: если не выбрала, идём дальше.
    """

    def test_step_20_did_not_choose_sleep(self):
        assert is_forced_sleep(20, chose_sleep=False) is True

    def test_step_20_chose_sleep_not_forced(self):
        assert is_forced_sleep(20, chose_sleep=True) is False

    @pytest.mark.parametrize("step", [0, 5, 10, 15, 19])
    def test_before_20_not_forced(self, step):
        assert is_forced_sleep(step, chose_sleep=False) is False

    @pytest.mark.parametrize("step", [0, 5, 10, 15, 19])
    def test_before_20_chose_sleep_not_forced(self, step):
        assert is_forced_sleep(step, chose_sleep=True) is False

    def test_step_19_no_sleep_not_forced(self):
        # Ключевой случай: на 19 не поспал — не форсим, идём на 20.
        assert is_forced_sleep(19, chose_sleep=False) is False


# ─── diary_source ──────────────────────────────────────────

class TestDiarySource:
    """
    Выбрала спать → дневник пишет Бурт.
    Иначе (в т.ч. принудительный) → дневник пишет МИР.
    """

    def test_chose_sleep_returns_burt(self):
        assert diary_source(chose_sleep=True) == DIARY_SOURCE_BURT

    def test_forced_returns_world(self):
        assert diary_source(chose_sleep=False) == DIARY_SOURCE_WORLD


# ─── apply_sleep ───────────────────────────────────────────

class TestApplySleep:
    """
    При любом сне:
      - HP = hp_max;
      - MP = mp_max;
      - эффекты сняты (все, без исключений).
    """

    def test_hp_restored_to_max(self):
        hp, _, _ = apply_sleep(hp_max=20, mp_max=5)
        assert hp == 20

    def test_mp_restored_to_max(self):
        _, mp, _ = apply_sleep(hp_max=20, mp_max=5)
        assert mp == 5

    def test_effects_cleared(self):
        _, _, effects = apply_sleep(hp_max=20, mp_max=5)
        assert effects == []

    def test_level_1(self):
        hp, mp, effects = apply_sleep(hp_max=10, mp_max=3)
        assert hp == 10
        assert mp == 3
        assert effects == []

    def test_full_return_shape(self):
        result = apply_sleep(hp_max=30, mp_max=8)
        assert isinstance(result, tuple)
        assert len(result) == 3