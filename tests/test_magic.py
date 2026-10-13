"""Тесты для burt/magic.py — §9 «Магия» (чистая часть).

Что НЕ здесь (отложено):
    - статусы паладин/еретик      -> quests.py
    - цепочки квестов             -> quests.py
    - логика диалога с учителем   -> npc/loop
    - кара богов, паладин->убийца -> quests/npc

Что здесь:
    - константы каста
    - выбор стихии магом (1d4 при спавне учителя)
    - проверки лимитов слотов
    - проверка условий каста
    - соответствие «учитель -> что даёт»
    - механика «обучение = +1 уровень навыка» (§32, общая)

Модель данных (state.hidden.spells):
    element:    None | огонь | вода | земля | воздух
    alignment:  None | свет | тьма
"""
import pytest

from burt import magic


# ============================================================
# 1. КОНСТАНТЫ
# ============================================================

class TestConstants:
    def test_elements(self):
        assert magic.ELEMENTS == frozenset({
            "огонь", "вода", "земля", "воздух",
        })

    def test_alignments(self):
        assert magic.ALIGNMENTS == frozenset({"свет", "тьма"})

    def test_cast_mp_cost(self):
        assert magic.CAST_MP_COST == 1

    def test_cast_damage_min(self):
        assert magic.CAST_DAMAGE_MIN == 3

    def test_cast_damage_max(self):
        assert magic.CAST_DAMAGE_MAX == 6

    def test_skill_max_level(self):
        assert magic.SKILL_MAX_LEVEL == 10

    def test_max_spells(self):
        # 1 стихия + 1 алигмент = 2 заклинания за жизнь
        assert magic.MAX_SPELLS == 2


# ============================================================
# 2. ВЫБОР СТИХИИ МАГОМ — 1d4 ПРИ СПАВНЕ
# ============================================================

class TestRollMageElement:
    """§9: «маг — стихия (одна из четырёх), определяется 1d4 при спавне»."""

    @pytest.mark.parametrize("roll,expected", [
        (1, "огонь"),
        (2, "вода"),
        (3, "земля"),
        (4, "воздух"),
    ])
    def test_roll_to_element(self, roll, expected):
        rng = lambda: roll
        assert magic.roll_mage_element(rng) == expected

    def test_rng_called_exactly_once(self):
        calls = []

        def rng():
            calls.append(1)
            return 2

        magic.roll_mage_element(rng)
        assert len(calls) == 1

    def test_result_is_element(self):
        rng = lambda: 1
        result = magic.roll_mage_element(rng)
        assert result in magic.ELEMENTS


# ============================================================
# 3. УСЛОВИЯ КАСТА
# ============================================================

class TestCanCast:
    """§9: каст требует ТРИ условия — посох, заклинание, учитель."""

    def test_all_three(self):
        assert magic.can_cast(
            has_staff=True, has_spell=True, has_teacher=True,
        ) is True

    def test_no_staff(self):
        assert magic.can_cast(
            has_staff=False, has_spell=True, has_teacher=True,
        ) is False

    def test_no_spell(self):
        assert magic.can_cast(
            has_staff=True, has_spell=False, has_teacher=True,
        ) is False

    def test_no_teacher(self):
        assert magic.can_cast(
            has_staff=True, has_spell=True, has_teacher=False,
        ) is False

    def test_none(self):
        assert magic.can_cast(
            has_staff=False, has_spell=False, has_teacher=False,
        ) is False


# ============================================================
# 4. ОТКРЫТИЕ СТИХИИ — ЛИМИТ 1
# ============================================================

class TestCanLearnElement:
    """§9: 1 стихия за жизнь. Повторно не открывается."""

    def test_first_element(self):
        assert magic.can_learn_element(None, "огонь") is True

    @pytest.mark.parametrize("element", [
        "огонь", "вода", "земля", "воздух",
    ])
    def test_first_element_any(self, element):
        assert magic.can_learn_element(None, element) is True

    def test_same_element_again(self):
        # повторно не открывается
        assert magic.can_learn_element("огонь", "огонь") is False

    def test_second_different_element(self):
        # лимит 1 — вторую не даём
        assert magic.can_learn_element("огонь", "вода") is False

    def test_unknown_new_element(self):
        # мусорный вход — не падаем, просто False
        assert magic.can_learn_element(None, "хрень") is False

    def test_unknown_current_element(self):
        assert magic.can_learn_element("хрень", "огонь") is False


# ============================================================
# 5. ОТКРЫТИЕ АЛИГМЕНТА — ТЬМА / СВЕТ ВЗАИМОИСКЛЮЧАЮЩИЕ
# ============================================================

class TestCanLearnAlignment:
    """§9: 1 из пары тьма/свет. Обе — нельзя."""

    def test_first_alignment_light(self):
        assert magic.can_learn_alignment(None, "свет") is True

    def test_first_alignment_dark(self):
        assert magic.can_learn_alignment(None, "тьма") is True

    def test_same_alignment_again(self):
        assert magic.can_learn_alignment("свет", "свет") is False

    def test_opposite_alignment(self):
        # тьма/свет взаимоисключающие
        assert magic.can_learn_alignment("свет", "тьма") is False
        assert magic.can_learn_alignment("тьма", "свет") is False

    def test_unknown_new_alignment(self):
        assert magic.can_learn_alignment(None, "серость") is False

    def test_unknown_current_alignment(self):
        assert magic.can_learn_alignment("серость", "свет") is False


# ============================================================
# 6. СЛОТЫ ЗАКЛИНАНИЙ — ОБЩИЙ ЛИМИТ 2
# ============================================================

class TestTotalSpells:
    def test_none(self):
        assert magic.total_spells(None, None) == 0

    def test_element_only(self):
        assert magic.total_spells("огонь", None) == 1

    def test_alignment_only(self):
        assert magic.total_spells(None, "свет") == 1

    def test_both(self):
        assert magic.total_spells("огонь", "свет") == 2


# ============================================================
# 7. УЧИТЕЛЯ — КТО ЧТО ДАЁТ
# ============================================================

class TestTeacherKind:
    """§9: маг -> стихия, служитель -> свет, чернокнижник -> тьма."""

    def test_mage_gives_element(self):
        assert magic.TEACHER_KIND["маг"] == "element"

    def test_priest_gives_light(self):
        assert magic.TEACHER_KIND["служитель"] == "свет"

    def test_warlock_gives_dark(self):
        assert magic.TEACHER_KIND["чернокнижник"] == "тьма"

    def test_exactly_three_teachers(self):
        assert len(magic.TEACHER_KIND) == 3


# ============================================================
# 8. ОБУЧЕНИЕ — +1 УРОВЕНЬ НАВЫКА (§32)
# ============================================================

class TestNextSkillLevel:
    """§32: обучение = 1 раз за мир, +1 к навыку бесплатно.
    Кап — 10 (§8: «X/10»)."""

    @pytest.mark.parametrize("current,expected", [
        (0, 1),
        (1, 2),
        (2, 3),
        (5, 6),
        (8, 9),
        (9, 10),
    ])
    def test_level_up(self, current, expected):
        assert magic.next_skill_level(current) == expected

    def test_cap_at_max(self):
        assert magic.next_skill_level(10) == 10

    def test_cap_above_max(self):
        # защита от мусора
        assert magic.next_skill_level(15) == 10