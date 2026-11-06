"""Тесты sensory.format_combat_report — §23.

Боевой сенсорный отчёт. Отдельная функция, format_sensory_report
не трогает. По §23:

    [БОЙ]
    Противник: гоблин (или волк_1, волк_2)
    Твой ход.

Правила:
- HP врагов НЕ показываем, урон НЕ показываем.
- Мёртвых помечаем "(Мёртв)".
- Раунд НЕ выводим, инициативу НЕ выводим.
- Меню собирается из реально доступных действий:
  - атаковать <цель> — по строке на каждого живого врага;
  - блокировать — если есть живые;
  - бежать — если есть живые и среди них нет no_flee;
  - кастовать — если burt.spells_available.

Тесты используют ENEMIES из bestiary, чтобы не быть
привязанными к конкретным именам/ключам.
"""

import re
import pytest

from burt import sensory
from burt.combat import CombatState, EnemyInstance, BurtStats
from burt.bestiary import ENEMIES


# ─── хелперы ────────────────────────────────────────────────

def _key_any():
    return next(iter(ENEMIES))


def _key_no_flee():
    return next(
        k for k, e in ENEMIES.items()
        if e.tags and "no_flee" in e.tags
    )


def _key_with_flee():
    return next(
        k for k, e in ENEMIES.items()
        if not (e.tags and "no_flee" in e.tags)
    )


def _enemy(key, eid=None, alive=True):
    t = ENEMIES[key]
    return EnemyInstance(
        id=eid or f"{key}_1",
        key=key,
        hp=t.hp_max if alive else 0,
        hp_max=t.hp_max,
        mp=t.mp_max,
        mp_max=t.mp_max,
        alive=alive,
    )


def _combat(*enemies, initiative="burt"):
    return CombatState(enemies=list(enemies), initiative=initiative)


def _burt(spells=False):
    return BurtStats(
        hp=10, hp_max=10, mp=3, mp_max=3,
        spells_available=spells,
    )


def _report(combat, burt=None):
    return sensory.format_combat_report(combat, burt or _burt())


# ─── структура ─────────────────────────────────────────────

class TestStructure:
    def test_returns_string(self):
        k = _key_any()
        assert isinstance(_report(_combat(_enemy(k))), str)

    def test_starts_with_combat_header(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert out.startswith("[БОЙ]")

    def test_has_protivnik_line(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "Противник:" in out

    def test_has_tvoy_hod(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "Твой ход." in out

    def test_no_trailing_newline(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert not out.endswith("\n")

    def test_blank_line_between_state_and_menu(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "\n\n" in out


# ─── противники ────────────────────────────────────────────

class TestOpponents:
    def test_single_enemy_name(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert ENEMIES[k].name in out

    def test_two_same_numbered(self):
        k = _key_any()
        out = _report(_combat(
            _enemy(k, f"{k}_1"), _enemy(k, f"{k}_2"),
        ))
        n = ENEMIES[k].name
        assert f"{n}_1" in out
        assert f"{n}_2" in out

    def test_two_different_not_numbered(self):
        keys = list(ENEMIES)[:2]
        k0, k1 = keys[0], keys[1]
        out = _report(_combat(_enemy(k0), _enemy(k1)))
        n0, n1 = ENEMIES[k0].name, ENEMIES[k1].name
        assert n0 in out
        assert n1 in out
        assert f"{n0}_1" not in out
        assert f"{n1}_1" not in out

    def test_dead_marked(self):
        k = _key_any()
        out = _report(_combat(_enemy(k, f"{k}_1", alive=False)))
        assert "Мёртв" in out

    def test_dead_keeps_number_when_multiple(self):
        k = _key_any()
        out = _report(_combat(
            _enemy(k, f"{k}_1", alive=False),
            _enemy(k, f"{k}_2", alive=True),
        ))
        n = ENEMIES[k].name
        assert f"{n}_1" in out and "Мёртв" in out
        assert f"{n}_2" in out

    def test_numbering_stable_after_death(self):
        # убили первого — второй остаётся волк_2, не превращается в волк
        k = _key_any()
        out = _report(_combat(
            _enemy(k, f"{k}_1", alive=False),
            _enemy(k, f"{k}_2", alive=True),
        ))
        n = ENEMIES[k].name
        assert f"{n}_2" in out


# ─── не протекает скрытое ──────────────────────────────────

class TestHiddenInfo:
    def test_no_hp_word(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "HP" not in out

    def test_no_damage_word(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        for word in ("урон", "Урон", "damage"):
            assert word not in out

    def test_no_hp_numbers_pattern(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert not re.search(r"\d+\s*/\s*\d+", out)

    def test_no_round_word(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "Раунд" not in out
        assert "раунд" not in out

    def test_no_initiative_leak(self):
        k = _key_any()
        out = _report(_combat(_enemy(k), initiative="enemy"))
        assert "инициатив" not in out
        assert "Инициатив" not in out

    def test_no_ambush_word(self):
        k = _key_any()
        out = _report(_combat(_enemy(k), initiative="enemy"))
        assert "асад" not in out  # "засада" / "Засада"


# ─── меню ──────────────────────────────────────────────────

class TestMenu:
    def test_attack_single_uses_name(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert f"атаковать {ENEMIES[k].name}" in out

    def test_attack_multiple_lists_each_alive(self):
        k = _key_any()
        out = _report(_combat(
            _enemy(k, f"{k}_1"), _enemy(k, f"{k}_2"),
        ))
        n = ENEMIES[k].name
        assert f"атаковать {n}_1" in out
        assert f"атаковать {n}_2" in out

    def test_attack_skips_dead(self):
        k = _key_any()
        out = _report(_combat(
            _enemy(k, f"{k}_1", alive=False),
            _enemy(k, f"{k}_2", alive=True),
        ))
        n = ENEMIES[k].name
        assert f"атаковать {n}_2" in out
        assert f"атаковать {n}_1" not in out

    def test_block_present(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)))
        assert "блокировать" in out

    def test_flee_present_for_normal(self):
        k = _key_with_flee()
        out = _report(_combat(_enemy(k, f"{k}_1")))
        assert "бежать" in out

    def test_flee_absent_for_no_flee(self):
        k = _key_no_flee()
        out = _report(_combat(_enemy(k, f"{k}_1")))
        assert "бежать" not in out

    def test_cast_absent_by_default(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)), _burt(spells=False))
        assert "кастовать" not in out

    def test_cast_present_when_available(self):
        k = _key_any()
        out = _report(_combat(_enemy(k)), _burt(spells=True))
        assert "кастовать" in out

    def test_menu_order_attacks_first(self):
        keys = [
            k for k, e in ENEMIES.items()
            if not (e.tags and "no_flee" in e.tags)
        ][:2]
        k0, k1 = keys[0], keys[1]
        out = _report(_combat(_enemy(k0), _enemy(k1)))
        idx_attack = out.index("атаковать")
        idx_block = out.index("блокировать")
        idx_flee = out.index("бежать")
        assert idx_attack < idx_block < idx_flee

    def test_cast_after_flee(self):
        k = _key_with_flee()
        out = _report(
            _combat(_enemy(k, f"{k}_1")),
            _burt(spells=True),
        )
        assert out.index("кастовать") > out.index("бежать")


# ─── граничные случаи ──────────────────────────────────────

class TestEdgeCases:
    def test_all_dead_no_attack_lines(self):
        k = _key_any()
        out = _report(_combat(_enemy(k, f"{k}_1", alive=False)))
        assert "атаковать" not in out

    def test_all_dead_no_block_no_flee(self):
        k = _key_any()
        out = _report(_combat(_enemy(k, f"{k}_1", alive=False)))
        assert "блокировать" not in out
        assert "бежать" not in out

    def test_all_dead_still_has_header_and_tvoy_hod(self):
        k = _key_any()
        out = _report(_combat(_enemy(k, f"{k}_1", alive=False)))
        assert out.startswith("[БОЙ]")
        assert "Твой ход." in out