"""
Тесты для burt/spawn.py — спавн врагов.

Источники: §21 (цифры врагов), §23 (инициатива, случайная встреча),
§32 (спавн по локациям).

Расклады кубика (1 — хуже всего, 6 — лучше всего):

  Лес:
    1-2 → гоблин-шаман (один)
    3   → гоблин (стая 1-3)
    4-5 → волк (стая 1-3)
    6   → кабан (один)

  Подземелье:
    1   → дракон
    2-3 → гоблин-шаман (один)
    4-6 → гоблин (стая 1-3)

  Поле: кабан (один).
  Степь: волк (стая).
  Болото: гоблин (стая).
  Река, дорога, деревня, храм: пусто.

  Размер стаи (гоблин и волк):
    1-2 → 3
    3-4 → 2
    5-6 → 1

ПРЕДПОЛОЖЕНИЕ (требует подтверждения):
  Засада — кубик на тип врага:
    1-3 → волк
    4-6 → гоблин
  Размер — по общему правилу для типа.
"""

import pytest

from burt.spawn import (
    PACK_ENEMIES,
    possible_enemies,
    roll_enemy_type,
    roll_pack_size,
    spawn_random,
    spawn_ambush,
    is_pack,
)


# ─── Константы ─────────────────────────────────────────────

class TestConstants:
    def test_pack_enemies(self):
        assert PACK_ENEMIES == frozenset({"goblin", "wolf"})


# ─── possible_enemies ──────────────────────────────────────

class TestPossibleEnemies:
    def test_forest(self):
        assert possible_enemies("forest") == frozenset(
            {"goblin", "goblin_shaman", "wolf", "boar"}
        )

    def test_dungeon(self):
        assert possible_enemies("dungeon") == frozenset(
            {"goblin", "goblin_shaman", "dragon"}
        )

    def test_field(self):
        assert possible_enemies("field") == frozenset({"boar"})

    def test_steppe(self):
        assert possible_enemies("steppe") == frozenset({"wolf"})

    def test_swamp(self):
        assert possible_enemies("swamp") == frozenset({"goblin"})

    @pytest.mark.parametrize(
        "location", ["river", "road", "village", "temple"]
    )
    def test_empty_locations(self, location):
        assert possible_enemies(location) == frozenset()


# ─── roll_enemy_type — лес ─────────────────────────────────

class TestRollEnemyTypeForest:
    @pytest.mark.parametrize("roll", [1, 2])
    def test_shaman(self, roll):
        assert roll_enemy_type("forest", roll) == "goblin_shaman"

    def test_goblin_on_3(self):
        assert roll_enemy_type("forest", 3) == "goblin"

    @pytest.mark.parametrize("roll", [4, 5])
    def test_wolf(self, roll):
        assert roll_enemy_type("forest", roll) == "wolf"

    def test_boar_on_6(self):
        assert roll_enemy_type("forest", 6) == "boar"


# ─── roll_enemy_type — подземелье ──────────────────────────

class TestRollEnemyTypeDungeon:
    def test_dragon_on_1(self):
        assert roll_enemy_type("dungeon", 1) == "dragon"

    @pytest.mark.parametrize("roll", [2, 3])
    def test_shaman(self, roll):
        assert roll_enemy_type("dungeon", roll) == "goblin_shaman"

    @pytest.mark.parametrize("roll", [4, 5, 6])
    def test_goblin(self, roll):
        assert roll_enemy_type("dungeon", roll) == "goblin"


# ─── roll_enemy_type — моно-локации ────────────────────────

class TestRollEnemyTypeSingle:
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_field_always_boar(self, roll):
        assert roll_enemy_type("field", roll) == "boar"

    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_steppe_always_wolf(self, roll):
        assert roll_enemy_type("steppe", roll) == "wolf"

    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_swamp_always_goblin(self, roll):
        assert roll_enemy_type("swamp", roll) == "goblin"


# ─── roll_enemy_type — пустые локации ──────────────────────

class TestRollEnemyTypeEmpty:
    @pytest.mark.parametrize(
        "location", ["river", "road", "village", "temple"]
    )
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_returns_none(self, location, roll):
        assert roll_enemy_type(location, roll) is None


# ─── roll_pack_size ────────────────────────────────────────

class TestRollPackSize:
    # Гоблин и волк — по общему правилу.

    @pytest.mark.parametrize("enemy", ["goblin", "wolf"])
    @pytest.mark.parametrize("roll", [1, 2])
    def test_pack_of_three(self, enemy, roll):
        assert roll_pack_size(enemy, roll) == 3

    @pytest.mark.parametrize("enemy", ["goblin", "wolf"])
    @pytest.mark.parametrize("roll", [3, 4])
    def test_pack_of_two(self, enemy, roll):
        assert roll_pack_size(enemy, roll) == 2

    @pytest.mark.parametrize("enemy", ["goblin", "wolf"])
    @pytest.mark.parametrize("roll", [5, 6])
    def test_pack_of_one(self, enemy, roll):
        assert roll_pack_size(enemy, roll) == 1

    # Одиночки — всегда 1, вне зависимости от кубика.

    @pytest.mark.parametrize("enemy", ["goblin_shaman", "boar", "dragon"])
    @pytest.mark.parametrize("roll", [1, 2, 3, 4, 5, 6])
    def test_single_always_one(self, enemy, roll):
        assert roll_pack_size(enemy, roll) == 1


# ─── is_pack ───────────────────────────────────────────────

class TestIsPack:
    def test_goblin_is_pack(self):
        assert is_pack("goblin") is True

    def test_wolf_is_pack(self):
        assert is_pack("wolf") is True

    @pytest.mark.parametrize(
        "enemy", ["goblin_shaman", "boar", "bandit", "bear", "dragon"]
    )
    def test_others_not_pack(self, enemy):
        assert is_pack(enemy) is False


# ─── spawn_random ──────────────────────────────────────────

class TestSpawnRandom:
    # Лес.

    def test_forest_shaman(self):
        # roll_type=1 → шаман, размер игнорируется.
        assert spawn_random("forest", 1, 5) == ["goblin_shaman"]

    def test_forest_goblin_pack_of_three(self):
        # roll_type=3 → гоблин, roll_size=1 → 3.
        assert spawn_random("forest", 3, 1) == ["goblin", "goblin", "goblin"]

    def test_forest_goblin_single(self):
        assert spawn_random("forest", 3, 6) == ["goblin"]

    def test_forest_wolf_pack_of_two(self):
        assert spawn_random("forest", 4, 3) == ["wolf", "wolf"]

    def test_forest_boar_single(self):
        assert spawn_random("forest", 6, 1) == ["boar"]

    # Подземелье.

    def test_dungeon_dragon(self):
        assert spawn_random("dungeon", 1, 1) == ["dragon"]

    def test_dungeon_shaman(self):
        assert spawn_random("dungeon", 3, 1) == ["goblin_shaman"]

    def test_dungeon_goblin_pack(self):
        assert spawn_random("dungeon", 6, 1) == ["goblin", "goblin", "goblin"]

    # Моно-локации.

    def test_field_boar(self):
        assert spawn_random("field", 1, 1) == ["boar"]

    def test_steppe_wolf_pack(self):
        assert spawn_random("steppe", 5, 1) == ["wolf", "wolf", "wolf"]

    def test_swamp_goblin(self):
        assert spawn_random("swamp", 6, 6) == ["goblin"]

    # Пустые локации.

    @pytest.mark.parametrize(
        "location", ["river", "road", "village", "temple"]
    )
    def test_empty_location_returns_empty_list(self, location):
        assert spawn_random(location, 1, 1) == []


# ─── spawn_ambush ──────────────────────────────────────────

class TestSpawnAmbush:
    """
    Засада: только гоблины или только волки.

    ПРЕДПОЛОЖЕНИЕ (требует подтверждения):
      1-3 → волк
      4-6 → гоблин
    """

    @pytest.mark.parametrize("roll", [1, 2, 3])
    def test_wolf_on_low_rolls(self, roll):
        assert spawn_ambush(roll, 5) == ["wolf"]

    @pytest.mark.parametrize("roll", [4, 5, 6])
    def test_goblin_on_high_rolls(self, roll):
        assert spawn_ambush(roll, 5) == ["goblin"]

    def test_wolf_pack_of_three(self):
        assert spawn_ambush(1, 1) == ["wolf", "wolf", "wolf"]

    def test_goblin_pack_of_two(self):
        assert spawn_ambush(6, 3) == ["goblin", "goblin"]

    def test_goblin_single(self):
        assert spawn_ambush(6, 6) == ["goblin"]


# ─── Валидация ─────────────────────────────────────────────

class TestValidation:
    @pytest.mark.parametrize("bad_roll", [0, 7, -1, 100])
    def test_roll_enemy_type_rejects_bad_roll(self, bad_roll):
        with pytest.raises(ValueError):
            roll_enemy_type("forest", bad_roll)

    @pytest.mark.parametrize("bad_roll", [0, 7, -1])
    def test_roll_pack_size_rejects_bad_roll(self, bad_roll):
        with pytest.raises(ValueError):
            roll_pack_size("goblin", bad_roll)

    @pytest.mark.parametrize("bad_roll", [0, 7, -1])
    def test_spawn_ambush_rejects_bad_roll_type(self, bad_roll):
        with pytest.raises(ValueError):
            spawn_ambush(bad_roll, 1)

    @pytest.mark.parametrize("bad_roll", [0, 7, -1])
    def test_spawn_ambush_rejects_bad_roll_size(self, bad_roll):
        with pytest.raises(ValueError):
            spawn_ambush(1, bad_roll)

    def test_unknown_location_returns_none(self):
        # Локации вне таблицы — не ошибка, а пустота.
        assert roll_enemy_type("swimming_pool", 1) is None

    def test_unknown_location_possible_enemies_empty(self):
        assert possible_enemies("swimming_pool") == frozenset()