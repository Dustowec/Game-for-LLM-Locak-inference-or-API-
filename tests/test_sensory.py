"""Тесты sensory.py — §25.

Сенсорный отчёт — plain-text, секции в квадратных скобках.
Собирается из visible state (§30).

Формат (§25):
    [СОСТОЯНИЕ]
    HP: 12/20 | MP: 3/5
    Голод: сыт | Сон: 15/20
    Дата: 7 день
    Эффекты: благословлён

    [МЕСТО]
    Лесная тропа
    Выходы: север, восток, юг

    [РУКИ]
    Меч — 1шт

    [КОШЕЛЁК]
    3 сер., 5 мед.

    [НАВЫКИ]
    Владение дубиной 1/10
"""

import config
from burt import sensory


# ---------------------------------------------------------------------
# Хелпер: базовый visible по §30
# ---------------------------------------------------------------------

def _visible(**overrides):
    base = {
        "hp": 12, "hp_max": 20,
        "mp": 3, "mp_max": 5,
        "eat": True,
        "sleep_counter": 15,
        "date": "7 день",
        "effects": [],
        "location": {
            "name": "Лесная тропа",
            "exits": ["north", "east", "south"],
        },
        "inventory": [],
        "wallet": {"gold": 0, "silver": 0, "copper": 0},
        "skills_visible": [],
        "state": "exploring",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------
# Структура вывода
# ---------------------------------------------------------------------

class TestStructure:
    def test_returns_string(self):
        assert isinstance(sensory.format_sensory_report(_visible()), str)

    def test_has_all_five_sections(self):
        out = sensory.format_sensory_report(_visible())
        for header in ("[СОСТОЯНИЕ]", "[МЕСТО]", "[РУКИ]",
                       "[КОШЕЛЁК]", "[НАВЫКИ]"):
            assert header in out

    def test_sections_separated_by_blank_line(self):
        out = sensory.format_sensory_report(_visible())
        assert "\n\n[МЕСТО]" in out
        assert "\n\n[РУКИ]" in out
        assert "\n\n[КОШЕЛЁК]" in out
        assert "\n\n[НАВЫКИ]" in out

    def test_no_trailing_newline(self):
        out = sensory.format_sensory_report(_visible())
        assert not out.endswith("\n")

    def test_section_order(self):
        out = sensory.format_sensory_report(_visible())
        idx = [
            out.index("[СОСТОЯНИЕ]"),
            out.index("[МЕСТО]"),
            out.index("[РУКИ]"),
            out.index("[КОШЕЛЁК]"),
            out.index("[НАВЫКИ]"),
        ]
        assert idx == sorted(idx)


# ---------------------------------------------------------------------
# [СОСТОЯНИЕ]
# ---------------------------------------------------------------------

class TestStateSection:
    def test_hp_numbers_mode(self):
        out = sensory.format_sensory_report(_visible(hp=12, hp_max=20))
        assert "HP: 12/20" in out

    def test_mp_always_numbers(self):
        out = sensory.format_sensory_report(_visible(mp=3, mp_max=5))
        assert "MP: 3/5" in out

    def test_hp_and_mp_on_same_line(self):
        out = sensory.format_sensory_report(_visible())
        assert "HP: 12/20 | MP: 3/5" in out

    def test_hunger_syt(self):
        out = sensory.format_sensory_report(_visible(eat=True))
        assert "Голод: сыт" in out

    def test_hunger_goloden(self):
        out = sensory.format_sensory_report(_visible(eat=False))
        assert "Голод: голоден" in out

    def test_sleep_timer_shown(self):
        out = sensory.format_sensory_report(_visible(sleep_counter=15))
        assert "Сон: 15/20" in out

    def test_sleep_zero(self):
        out = sensory.format_sensory_report(_visible(sleep_counter=0))
        assert "Сон: 0/20" in out

    def test_hunger_and_sleep_same_line(self):
        out = sensory.format_sensory_report(
            _visible(eat=True, sleep_counter=15)
        )
        assert "Голод: сыт | Сон: 15/20" in out

    def test_date_shown(self):
        out = sensory.format_sensory_report(_visible(date="7 день"))
        assert "Дата: 7 день" in out

    def test_effects_empty_no_line(self):
        out = sensory.format_sensory_report(_visible(effects=[]))
        assert "Эффекты:" not in out

    def test_effect_blessed_translated(self):
        out = sensory.format_sensory_report(_visible(effects=["blessed"]))
        assert "Эффекты: благословлён" in out

    def test_effect_cursed_translated(self):
        out = sensory.format_sensory_report(_visible(effects=["cursed"]))
        assert "Эффекты: проклят" in out

    def test_effects_multiple(self):
        out = sensory.format_sensory_report(
            _visible(effects=["blessed", "cursed"])
        )
        assert "Эффекты: благословлён, проклят" in out

    def test_no_english_blessed(self):
        out = sensory.format_sensory_report(_visible(effects=["blessed"]))
        assert "blessed" not in out

    def test_no_english_cursed(self):
        out = sensory.format_sensory_report(_visible(effects=["cursed"]))
        assert "cursed" not in out


# ---------------------------------------------------------------------
# [СОСТОЯНИЕ] — качественный HP (§24)
# ---------------------------------------------------------------------

class TestStateHpQualitative:
    def _out(self, monkeypatch, hp, hp_max):
        monkeypatch.setattr(config, "HP_DISPLAY", "qualitative")
        return sensory.format_sensory_report(
            _visible(hp=hp, hp_max=hp_max)
        )

    def test_full_hp(self, monkeypatch):
        assert "HP: в порядке" in self._out(monkeypatch, 20, 20)

    def test_exactly_80_percent(self, monkeypatch):
        assert "HP: в порядке" in self._out(monkeypatch, 16, 20)

    def test_just_below_80(self, monkeypatch):
        assert "HP: нормально" in self._out(monkeypatch, 15, 20)

    def test_exactly_50_percent(self, monkeypatch):
        assert "HP: нормально" in self._out(monkeypatch, 10, 20)

    def test_just_below_50(self, monkeypatch):
        assert "HP: опасно, мало HP" in self._out(monkeypatch, 9, 20)

    def test_exactly_25_percent(self, monkeypatch):
        assert "HP: опасно, мало HP" in self._out(monkeypatch, 5, 20)

    def test_just_below_25(self, monkeypatch):
        assert "HP: критично" in self._out(monkeypatch, 4, 20)

    def test_zero_hp(self, monkeypatch):
        assert "HP: критично" in self._out(monkeypatch, 0, 20)

    def test_mp_still_numbers(self, monkeypatch):
        monkeypatch.setattr(config, "HP_DISPLAY", "qualitative")
        out = sensory.format_sensory_report(
            _visible(hp=4, hp_max=20, mp=3, mp_max=5)
        )
        assert "MP: 3/5" in out


# ---------------------------------------------------------------------
# [СОСТОЯНИЕ] — SHOW_DATE / SHOW_SLEEP_TIMER
# ---------------------------------------------------------------------

class TestStateFlags:
    def test_show_date_false_hides_date(self, monkeypatch):
        monkeypatch.setattr(config, "SHOW_DATE", False)
        out = sensory.format_sensory_report(_visible(date="7 день"))
        assert "Дата:" not in out

    def test_show_sleep_timer_false_qualitative(self, monkeypatch):
        monkeypatch.setattr(config, "SHOW_SLEEP_TIMER", False)
        out = sensory.format_sensory_report(_visible(sleep_counter=15))
        assert "15/20" not in out
        assert "Сон:" in out

    def test_show_sleep_timer_false_bodr(self, monkeypatch):
        monkeypatch.setattr(config, "SHOW_SLEEP_TIMER", False)
        out = sensory.format_sensory_report(_visible(sleep_counter=5))
        assert "Сон: бодр" in out

    def test_show_sleep_timer_false_ustal(self, monkeypatch):
        monkeypatch.setattr(config, "SHOW_SLEEP_TIMER", False)
        out = sensory.format_sensory_report(_visible(sleep_counter=19))
        assert "Сон: устал" in out


# ---------------------------------------------------------------------
# [МЕСТО]
# ---------------------------------------------------------------------

class TestLocationSection:
    def test_location_name(self):
        out = sensory.format_sensory_report(
            _visible(location={"name": "Лесная тропа", "exits": ["north"]})
        )
        assert "Лесная тропа" in out

    def test_exits_translated(self):
        out = sensory.format_sensory_report(
            _visible(location={
                "name": "X",
                "exits": ["north", "east", "south"],
            })
        )
        assert "Выходы: север, восток, юг" in out

    def test_exits_all_four(self):
        out = sensory.format_sensory_report(
            _visible(location={
                "name": "X",
                "exits": ["north", "east", "south", "west"],
            })
        )
        assert "Выходы: север, восток, юг, запад" in out

    def test_no_english_directions(self):
        out = sensory.format_sensory_report(
            _visible(location={
                "name": "X",
                "exits": ["north", "east", "south", "west"],
            })
        )
        for en in ("north", "east", "south", "west"):
            assert en not in out

    def test_single_exit(self):
        out = sensory.format_sensory_report(
            _visible(location={"name": "X", "exits": ["south"]})
        )
        assert "Выходы: юг" in out

    def test_no_exits_no_line(self):
        # защита: если выходов нет (в норме не бывает), строку не выводим
        out = sensory.format_sensory_report(
            _visible(location={"name": "X", "exits": []})
        )
        assert "Выходы:" not in out


# ---------------------------------------------------------------------
# [РУКИ]
# ---------------------------------------------------------------------

class TestInventorySection:
    def _chunk(self, out):
        idx = out.index("[РУКИ]")
        return out[idx:].split("[КОШЕЛЁК]")[0]

    def test_empty_shows_pusto(self):
        out = sensory.format_sensory_report(_visible(inventory=[]))
        assert "пусто" in self._chunk(out)

    def test_single_item(self):
        out = sensory.format_sensory_report(
            _visible(inventory=[{"name": "меч", "count": 1}])
        )
        assert "Меч — 1шт" in out

    def test_two_items(self):
        out = sensory.format_sensory_report(
            _visible(inventory=[
                {"name": "меч", "count": 1},
                {"name": "хлеб", "count": 2},
            ])
        )
        assert "Меч — 1шт" in out
        assert "Хлеб — 2шт" in out

    def test_item_capitalized(self):
        out = sensory.format_sensory_report(
            _visible(inventory=[{"name": "меч", "count": 1}])
        )
        assert "Меч" in out

    def test_only_first_letter_uppercase(self):
        out = sensory.format_sensory_report(
            _visible(inventory=[{"name": "фляга с водой", "count": 1}])
        )
        assert "Фляга с водой" in out

    def test_order_preserved(self):
        out = sensory.format_sensory_report(
            _visible(inventory=[
                {"name": "меч", "count": 1},
                {"name": "хлеб", "count": 2},
            ])
        )
        assert out.index("Меч") < out.index("Хлеб")


# ---------------------------------------------------------------------
# [КОШЕЛЁК]
# ---------------------------------------------------------------------

class TestWalletSection:
    def _out(self, **wallet):
        return sensory.format_sensory_report(_visible(wallet=wallet))

    def _chunk(self, out):
        idx = out.index("[КОШЕЛЁК]")
        return out[idx:].split("[НАВЫКИ]")[0]

    def test_empty_shows_pusto(self):
        out = self._out(gold=0, silver=0, copper=0)
        assert "пусто" in self._chunk(out)

    def test_only_copper(self):
        out = self._out(gold=0, silver=0, copper=5)
        assert "5 мед." in out

    def test_only_silver(self):
        out = self._out(gold=0, silver=3, copper=0)
        assert "3 сер." in out

    def test_only_gold(self):
        out = self._out(gold=1, silver=0, copper=0)
        assert "1 зол." in out

    def test_silver_and_copper(self):
        out = self._out(gold=0, silver=3, copper=5)
        assert "3 сер., 5 мед." in out

    def test_all_three(self):
        out = self._out(gold=1, silver=3, copper=5)
        assert "1 зол., 3 сер., 5 мед." in out

    def test_gold_and_copper_skip_silver(self):
        out = self._out(gold=2, silver=0, copper=5)
        assert "2 зол., 5 мед." in out
        assert "0 сер." not in out

    def test_zero_values_not_shown(self):
        out = self._out(gold=0, silver=5, copper=0)
        assert "зол." not in out
        assert "мед." not in out


# ---------------------------------------------------------------------
# [НАВЫКИ]
# ---------------------------------------------------------------------

class TestSkillsSection:
    def _chunk(self, out):
        return out[out.index("[НАВЫКИ]"):]

    def test_empty_shows_pusto(self):
        out = sensory.format_sensory_report(_visible(skills_visible=[]))
        assert "пусто" in self._chunk(out)

    def test_single_skill(self):
        out = sensory.format_sensory_report(
            _visible(skills_visible=[
                {"name": "Владение дубиной", "level": 1, "max": 10},
            ])
        )
        assert "Владение дубиной 1/10" in out

    def test_two_skills(self):
        out = sensory.format_sensory_report(
            _visible(skills_visible=[
                {"name": "Владение дубиной", "level": 2, "max": 10},
                {"name": "Скрытность", "level": 1, "max": 10},
            ])
        )
        assert "Владение дубиной 2/10" in out
        assert "Скрытность 1/10" in out

    def test_order_preserved(self):
        out = sensory.format_sensory_report(
            _visible(skills_visible=[
                {"name": "А", "level": 1, "max": 10},
                {"name": "Б", "level": 1, "max": 10},
            ])
        )
        assert out.index("А 1/10") < out.index("Б 1/10")


# ---------------------------------------------------------------------
# Полный отчёт — пример из §25
# ---------------------------------------------------------------------

class TestFullReport:
    def test_example_from_spec(self):
        visible = _visible(
            hp=12, hp_max=20,
            mp=3, mp_max=5,
            eat=True,
            sleep_counter=15,
            date="7 день",
            effects=["blessed"],
            location={
                "name": "Лесная тропа",
                "exits": ["north", "east", "south"],
            },
            inventory=[
                {"name": "меч", "count": 1},
                {"name": "хлеб", "count": 2},
            ],
            wallet={"gold": 0, "silver": 3, "copper": 5},
            skills_visible=[
                {"name": "Владение дубиной", "level": 1, "max": 10},
            ],
        )
        expected = (
            "[СОСТОЯНИЕ]\n"
            "HP: 12/20 | MP: 3/5\n"
            "Голод: сыт | Сон: 15/20\n"
            "Дата: 7 день\n"
            "Эффекты: благословлён\n"
            "\n"
            "[МЕСТО]\n"
            "Лесная тропа\n"
            "Выходы: север, восток, юг\n"
            "\n"
            "[РУКИ]\n"
            "Меч — 1шт\n"
            "Хлеб — 2шт\n"
            "\n"
            "[КОШЕЛЁК]\n"
            "3 сер., 5 мед.\n"
            "\n"
            "[НАВЫКИ]\n"
            "Владение дубиной 1/10"
        )
        assert sensory.format_sensory_report(visible) == expected