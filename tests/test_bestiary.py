"""
Тесты для burt/bestiary.py — справочник врагов §21.

Чистые данные. Никакой логики, только таблица.
"""

import pytest

from burt.bestiary import ENEMIES, Enemy


# ─── Все враги на месте ────────────────────────────────────

class TestEnemyList:
    EXPECTED = {
        "goblin", "goblin_shaman", "wolf", "boar",
        "bandit", "bear", "dragon",
    }

    def test_all_enemies_present(self):
        assert set(ENEMIES.keys()) == self.EXPECTED

    def test_every_enemy_is_dataclass(self):
        for key, enemy in ENEMIES.items():
            assert isinstance(enemy, Enemy), f"{key} is not Enemy"

    def test_key_matches_dict_key(self):
        for key, enemy in ENEMIES.items():
            assert enemy.key == key


# ─── Цифры §21 ─────────────────────────────────────────────

class TestGoblin:
    def test_hp(self):
        assert ENEMIES["goblin"].hp_max == 6

    def test_damage(self):
        e = ENEMIES["goblin"]
        assert (e.damage_min, e.damage_max) == (1, 2)

    def test_weapon(self):
        assert ENEMIES["goblin"].weapon == "кинжал гоблина"

    def test_no_spell(self):
        assert ENEMIES["goblin"].spell_damage_min is None
        assert ENEMIES["goblin"].spell_damage_max is None
        assert ENEMIES["goblin"].spell_cost is None


class TestGoblinShaman:
    def test_hp(self):
        assert ENEMIES["goblin_shaman"].hp_max == 8

    def test_mp(self):
        assert ENEMIES["goblin_shaman"].mp_max == 5

    def test_staff_damage(self):
        e = ENEMIES["goblin_shaman"]
        assert (e.damage_min, e.damage_max) == (0, 1)

    def test_weapon(self):
        assert ENEMIES["goblin_shaman"].weapon == "колдовской посох гоблина"

    def test_spell_damage(self):
        e = ENEMIES["goblin_shaman"]
        assert (e.spell_damage_min, e.spell_damage_max) == (3, 6)

    def test_spell_cost(self):
        assert ENEMIES["goblin_shaman"].spell_cost == 1

    def test_staff_penalty_tag(self):
        assert "staff_penalty" in ENEMIES["goblin_shaman"].tags


class TestWolf:
    def test_hp(self):
        assert ENEMIES["wolf"].hp_max == 8

    def test_damage(self):
        e = ENEMIES["wolf"]
        assert (e.damage_min, e.damage_max) == (1, 3)

    def test_pack_tag(self):
        assert "pack" in ENEMIES["wolf"].tags


class TestBoar:
    def test_hp(self):
        assert ENEMIES["boar"].hp_max == 12

    def test_damage(self):
        e = ENEMIES["boar"]
        assert (e.damage_min, e.damage_max) == (1, 3)

    def test_wounded_prey_tag(self):
        # Атакует только если Бурт ранен (§21, уточнено автором).
        assert "wounded_prey" in ENEMIES["boar"].tags


class TestBandit:
    def test_hp(self):
        assert ENEMIES["bandit"].hp_max == 10

    def test_damage(self):
        e = ENEMIES["bandit"]
        assert (e.damage_min, e.damage_max) == (2, 4)

    def test_weapon(self):
        assert ENEMIES["bandit"].weapon == "меч"


class TestBear:
    def test_hp(self):
        assert ENEMIES["bear"].hp_max == 18

    def test_damage(self):
        e = ENEMIES["bear"]
        assert (e.damage_min, e.damage_max) == (5, 9)

    def test_passive_tag(self):
        # Медведь не атакует сам (§21, уточнено автором).
        assert "passive" in ENEMIES["bear"].tags


class TestDragon:
    def test_hp(self):
        assert ENEMIES["dragon"].hp_max == 60

    def test_bite_damage(self):
        e = ENEMIES["dragon"]
        assert (e.damage_min, e.damage_max) == (16, 22)

    def test_breath_damage(self):
        e = ENEMIES["dragon"]
        assert (e.breath_damage_min, e.breath_damage_max) == (12, 18)

    def test_breath_max(self):
        assert ENEMIES["dragon"].breath_max == 3

    def test_no_flee_tag(self):
        assert "no_flee" in ENEMIES["dragon"].tags