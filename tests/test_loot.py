"""
Тесты для burt/loot.py — §22 ТЗ v0.7.0.

Лут с врагов. Вызывается ПОСЛЕ боя, для всех убитых врагов.
При бегстве Бурта лута нет (решает оркестратор, не loot.py).

Формат дропа — список словарей, совместимый с инвентарём state:
  [{"name": "кинжал гоблина", "count": 1}, ...]

Медяки — отдельно, в поле coins_copper. Оркестратор кладёт их в кошелёк.

ПРЕДПОЛОЖЕНИЯ (требуют подтверждения):
  1. Волк, кабан, медведь попадают в общую таблицу «животные».
  2. Дракон выдаёт весь лут без кубика.
  3. «5 медяков» с бандита — деньги, не предмет.
  4. Лут считается на каждого убитого врага отдельным броском.
"""

import pytest

from burt.loot import (
    LootDrop,
    roll_loot,
    collect_loot,
)


# ─── Вспомогательное ───────────────────────────────────────

def item_names(drop: LootDrop) -> list[str]:
    return [item["name"] for item in drop.items]


def total_items(drop: LootDrop) -> int:
    return sum(item["count"] for item in drop.items)


# ─── Гоблин — §22 ──────────────────────────────────────────

class TestGoblinLoot:
    @pytest.mark.parametrize("roll", [1, 2, 3, 4])
    def test_nothing_on_low_rolls(self, roll):
        drop = roll_loot("goblin", roll)
        assert drop.items == []
        assert drop.coins_copper == 0

    @pytest.mark.parametrize("roll", [5, 6])
    def test_goblin_dagger_on_high_rolls(self, roll):
        drop = roll_loot("goblin", roll)
        assert item_names(drop) == ["кинжал гоблина"]
        assert total_items(drop) == 1
        assert drop.coins_copper == 0


# ─── Гоблин-шаман — §22 ────────────────────────────────────

class TestShamanLoot:
    @pytest.mark.parametrize("roll", [1, 2, 3, 4])
    def test_nothing_on_low_rolls(self, roll):
        drop = roll_loot("goblin_shaman", roll)
        assert drop.items == []
        assert drop.coins_copper == 0

    @pytest.mark.parametrize("roll", [5, 6])
    def test_shaman_staff_on_high_rolls(self, roll):
        drop = roll_loot("goblin_shaman", roll)
        assert item_names(drop) == ["колдовской посох гоблина"]
        assert total_items(drop) == 1


# ─── Бандит — §22 ──────────────────────────────────────────

class TestBanditLoot:
    @pytest.mark.parametrize("roll", [1, 2])
    def test_bandage(self, roll):
        drop = roll_loot("bandit", roll)
        assert item_names(drop) == ["повязка"]
        assert total_items(drop) == 1
        assert drop.coins_copper == 0

    @pytest.mark.parametrize("roll", [3, 4])
    def test_coins(self, roll):
        drop = roll_loot("bandit", roll)
        assert drop.items == []
        assert drop.coins_copper == 5

    @pytest.mark.parametrize("roll", [5, 6])
    def test_low_quality_sword(self, roll):
        drop = roll_loot("bandit", roll)
        assert item_names(drop) == ["меч низкого качества"]
        assert total_items(drop) == 1


# ─── Животные (волк, кабан, медведь) — §22 ─────────────────

class TestAnimalLoot:
    ANIMALS = ["wolf", "boar", "bear"]

    @pytest.mark.parametrize("enemy", ANIMALS)
    @pytest.mark.parametrize("roll", [1, 2, 3])
    def test_nothing_on_low_rolls(self, enemy, roll):
        drop = roll_loot(enemy, roll)
        assert drop.items == []
        assert drop.coins_copper == 0

    @pytest.mark.parametrize("enemy", ANIMALS)
    @pytest.mark.parametrize("roll", [4, 5])
    def test_fangs(self, enemy, roll):
        drop = roll_loot(enemy, roll)
        assert item_names(drop) == ["клыки"]
        assert drop.items[0]["count"] == 2

    @pytest.mark.parametrize("enemy", ANIMALS)
    def test_pelt_on_6(self, enemy):
        drop = roll_loot(enemy, 6)
        assert item_names(drop) == ["шкура"]
        assert drop.items[0]["count"] == 1


# ─── Дракон — §22, без кубика ─────────────────────────────

class TestDragonLoot:
    def test_always_full_loot(self):
        drop = roll_loot("dragon", 1)
        names = set(item_names(drop))
        assert names == {"чешуя дракона", "драконьи клыки", "кость дракона"}

    def test_roll_ignored(self):
        # Кубик не влияет — дракон всегда выдаёт всё.
        drop_low = roll_loot("dragon", 1)
        drop_high = roll_loot("dragon", 6)
        assert drop_low.items == drop_high.items

    def test_dragon_fangs_count(self):
        drop = roll_loot("dragon", 1)
        fangs = next(i for i in drop.items if i["name"] == "драконьи клыки")
        assert fangs["count"] == 2

    def test_no_coins(self):
        drop = roll_loot("dragon", 1)
        assert drop.coins_copper == 0


# ─── collect_loot — несколько врагов ───────────────────────

class TestCollectLoot:
    def test_empty_list_returns_empty_drop(self):
        drop = collect_loot([], [])
        assert drop.items == []
        assert drop.coins_copper == 0

    def test_single_kill(self):
        drop = collect_loot(["goblin"], [5])
        assert item_names(drop) == ["кинжал гоблина"]

    def test_multiple_kills_concatenate(self):
        # Два гоблина, оба с лутом.
        drop = collect_loot(["goblin", "goblin"], [5, 6])
        assert item_names(drop) == ["кинжал гоблина", "кинжал гоблина"]
        assert total_items(drop) == 2

    def test_coins_accumulate(self):
        # Два бандита, оба с деньгами.
        drop = collect_loot(["bandit", "bandit"], [3, 4])
        assert drop.coins_copper == 10

    def test_mixed_items_and_coins(self):
        # Гоблин с лутом + бандит с деньгами.
        drop = collect_loot(["goblin", "bandit"], [5, 3])
        assert item_names(drop) == ["кинжал гоблина"]
        assert drop.coins_copper == 5

    def test_length_mismatch_raises(self):
        with pytest.raises(ValueError):
            collect_loot(["goblin"], [5, 6])

    def test_concatenation_preserves_order(self):
        drop = collect_loot(
            ["goblin", "bandit", "wolf"],
            [5, 1, 6],
        )
        assert item_names(drop) == ["кинжал гоблина", "повязка", "шкура"]


# ─── Валидация ─────────────────────────────────────────────

class TestValidation:
    @pytest.mark.parametrize("bad_roll", [0, 7, -1, 100])
    def test_roll_loot_rejects_bad_roll(self, bad_roll):
        with pytest.raises(ValueError):
            roll_loot("goblin", bad_roll)

    def test_unknown_enemy_returns_empty_drop(self):
        # Неизвестный враг — не ошибка, пустой дроп.
        drop = roll_loot("unicorn", 5)
        assert drop.items == []
        assert drop.coins_copper == 0


# ─── LootDrop — форма ──────────────────────────────────────

class TestLootDropShape:
    def test_items_have_name_and_count(self):
        drop = roll_loot("goblin", 5)
        for item in drop.items:
            assert "name" in item
            assert "count" in item
            assert isinstance(item["count"], int)
            assert item["count"] > 0