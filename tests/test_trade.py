"""Тесты для burt/trade.py — §35 «Матрица торговли».

Формулы:
  модификатор локации (один раз при входе, живёт до конца сессии):
      1-2 -> +25%  (x1.25)
      3-4 ->  0%   (x1.00)
      5-6 -> -25%  (x0.75)
  покупка Буртом:  floor(base * mod)
  продажа Буртом:  floor(floor(base * 0.5) * mod)

Все цены — в МЕДЯКАХ (1 silver = 10 copper, 1 gold = 100 copper).
Округление ВНИЗ на каждом шаге.

Роли с торговлей (7):  elder, blacksmith, merchant, fisherman,
                       tavernkeeper, mage, necromancer
Роли без торговли (6): peasant, peasant_woman, child,
                       guard, veteran, cleric
Все роли с торговлей покупают ВСЁ.
"""
import pytest

from burt import trade


# ============================================================
# 1. МОДИФИКАТОР ЦЕНЫ ЛОКАЦИИ
# ============================================================

class TestLocationPriceModifier:
    """§35: 1-2 -> +25%, 3-4 -> базовая, 5-6 -> -25%."""

    @pytest.mark.parametrize("roll,expected", [
        (1, 1.25),
        (2, 1.25),
        (3, 1.00),
        (4, 1.00),
        (5, 0.75),
        (6, 0.75),
    ])
    def test_roll_to_modifier(self, roll, expected):
        rng = lambda: roll
        assert trade.roll_location_price_modifier(rng) == expected

    def test_rng_called_exactly_once(self):
        calls = []

        def rng():
            calls.append(1)
            return 3

        trade.roll_location_price_modifier(rng)
        assert len(calls) == 1

    def test_returns_float(self):
        rng = lambda: 4
        result = trade.roll_location_price_modifier(rng)
        assert isinstance(result, float)


# ============================================================
# 2. БАЗОВЫЕ ЦЕНЫ — ЧТО БУРТ ПОКУПАЕТ
# ============================================================

class TestBasePrices:
    """§35: цены покупки в медяках."""

    def test_bread(self):
        assert trade.BASE_PRICES["bread"] == 2

    def test_fish(self):
        assert trade.BASE_PRICES["fish"] == 2

    def test_dried_fish(self):
        assert trade.BASE_PRICES["dried_fish"] == 3

    def test_water_flask_small(self):
        # 2 copper
        assert trade.BASE_PRICES["waterskin"] == 2

    def test_water_flask_big(self):
        # 1 silver = 10 copper
        assert trade.BASE_PRICES["large_waterskin"] == 10

    def test_sleeping_bag(self):
        assert trade.BASE_PRICES["bedroll"] == 5

    def test_tavern_room(self):
        assert trade.BASE_PRICES["tavern_room"] == 5

    def test_club(self):
        # 1 silver = 10 copper
        assert trade.BASE_PRICES["club"] == 10

    def test_spear(self):
        # 2 silver = 20 copper
        assert trade.BASE_PRICES["spear"] == 20

    def test_sword_low(self):
        # 1 silver = 10 copper
        assert trade.BASE_PRICES["low_quality_sword"] == 10

    def test_sword_normal(self):
        # 3 silver = 30 copper
        assert trade.BASE_PRICES["ordinary_sword"] == 30

    def test_sword_high(self):
        # 6 silver = 60 copper
        assert trade.BASE_PRICES["high_quality_sword"] == 60

    def test_staff(self):
        # 1 gold = 100 copper
        assert trade.BASE_PRICES["staff"] == 100


# ============================================================
# 3. ЦЕНЫ ЛУТА — ЧТО БУРТ ПРОДАЁТ
# ============================================================

class TestLootPrices:
    """§35: цены лута в медяках (база для продажи)."""

    def test_goblin_dagger(self):
        assert trade.LOOT_PRICES["goblin_dagger"] == 3

    def test_goblin_staff(self):
        assert trade.LOOT_PRICES["goblin_staff"] == 6

    def test_bandage(self):
        assert trade.LOOT_PRICES["bandage"] == 1

    def test_fangs(self):
        # «fangs (2 pcs.)» — 3 copper за пару
        assert trade.LOOT_PRICES["fangs"] == 3

    def test_pelt(self):
        # 1 silver = 10 copper
        assert trade.LOOT_PRICES["pelt"] == 10

    def test_dragon_scale(self):
        # 10 gold = 1000 copper
        assert trade.LOOT_PRICES["dragon_scale"] == 1000

    def test_dragon_fangs(self):
        # 5 gold = 500 copper
        assert trade.LOOT_PRICES["dragon_fangs"] == 500

    def test_dragon_bone(self):
        # 10 gold = 1000 copper
        assert trade.LOOT_PRICES["dragon_bone"] == 1000


# ============================================================
# 4. ЦЕНА ПОКУПКИ
# ============================================================

class TestBuyPrice:
    """buy_price(base, mod) = floor(base * mod)."""

    def test_bread_base(self):
        assert trade.buy_price("bread", 1.0) == 2

    def test_bread_plus_25(self):
        # 2 * 1.25 = 2.5 -> 2
        assert trade.buy_price("bread", 1.25) == 2

    def test_bread_minus_25(self):
        # 2 * 0.75 = 1.5 -> 1
        assert trade.buy_price("bread", 0.75) == 1

    def test_sword_normal_base(self):
        assert trade.buy_price("ordinary_sword", 1.0) == 30

    def test_sword_normal_plus_25(self):
        # 30 * 1.25 = 37.5 -> 37
        assert trade.buy_price("ordinary_sword", 1.25) == 37

    def test_sword_normal_minus_25(self):
        # 30 * 0.75 = 22.5 -> 22
        assert trade.buy_price("ordinary_sword", 0.75) == 22

    def test_staff_plus_25(self):
        # 100 * 1.25 = 125
        assert trade.buy_price("staff", 1.25) == 125

    def test_rounds_down_always(self):
        # 3 * 1.25 = 3.75 -> 3, не 4
        assert trade.buy_price("dried_fish", 1.25) == 3

    def test_unknown_item_raises(self):
        with pytest.raises(KeyError):
            trade.buy_price("нет такого предмета", 1.0)

    def test_loot_not_buyable(self):
        # goblin_dagger — лут, Бурт его НЕ покупает
        with pytest.raises(KeyError):
            trade.buy_price("goblin_dagger", 1.0)


# ============================================================
# 5. ЦЕНА ПРОДАЖИ
# ============================================================

class TestSellPrice:
    """sell_price(base, mod) = floor(floor(base * 0.5) * mod)."""

    def test_bread_sell_base(self):
        # floor(floor(2 * 0.5) * 1.0) = floor(1 * 1) = 1
        assert trade.sell_price("bread", 1.0) == 1

    def test_sword_normal_sell_base(self):
        # floor(floor(30 * 0.5) * 1.0) = floor(15 * 1) = 15
        assert trade.sell_price("ordinary_sword", 1.0) == 15

    def test_sword_normal_sell_plus(self):
        # floor(15 * 1.25) = floor(18.75) = 18
        assert trade.sell_price("ordinary_sword", 1.25) == 18

    def test_sword_normal_sell_minus(self):
        # floor(15 * 0.75) = floor(11.25) = 11
        assert trade.sell_price("ordinary_sword", 0.75) == 11

    def test_goblin_dagger_sell_base(self):
        # floor(floor(3 * 0.5) * 1.0) = floor(1 * 1) = 1
        assert trade.sell_price("goblin_dagger", 1.0) == 1

    def test_goblin_dagger_sell_plus(self):
        # floor(1 * 1.25) = 1
        assert trade.sell_price("goblin_dagger", 1.25) == 1

    def test_goblin_dagger_sell_minus(self):
        # floor(1 * 0.75) = 0
        assert trade.sell_price("goblin_dagger", 0.75) == 0

    def test_bandage_always_zero(self):
        # floor(floor(1 * 0.5) * mod) = 0 всегда
        # bandage за 1 copper в продаже уходит за 0
        assert trade.sell_price("bandage", 1.0) == 0
        assert trade.sell_price("bandage", 1.25) == 0
        assert trade.sell_price("bandage", 0.75) == 0

    def test_dragon_scale_sell_base(self):
        # floor(floor(1000 * 0.5) * 1.0) = 500
        assert trade.sell_price("dragon_scale", 1.0) == 500

    def test_dragon_scale_sell_plus(self):
        # floor(500 * 1.25) = 625
        assert trade.sell_price("dragon_scale", 1.25) == 625

    def test_pelt_sell_base(self):
        # floor(floor(10 * 0.5) * 1.0) = 5
        assert trade.sell_price("pelt", 1.0) == 5

    def test_unknown_item_raises(self):
        with pytest.raises(KeyError):
            trade.sell_price("нет такого предмета", 1.0)

    def test_loot_sellable(self):
        assert trade.sell_price("goblin_staff", 1.0) == 3

    def test_regular_item_sellable(self):
        # Бурт может продать обратно bread
        assert trade.sell_price("bread", 1.0) == 1


# ============================================================
# 6. РОЛИ С ТОРГОВЛЕЙ И БЕЗ
# ============================================================

class TestTradeRoles:
    """§35: 7 ролей с торговлей, 6 без."""

    def test_count_with_trade(self):
        assert len(trade.TRADE_ROLES) == 7

    @pytest.mark.parametrize("role", [
        "elder", "blacksmith", "merchant", "fisherman",
        "tavernkeeper", "mage", "necromancer",
    ])
    def test_role_has_trade(self, role):
        assert role in trade.TRADE_ROLES

    @pytest.mark.parametrize("role", [
        "peasant", "peasant_woman", "child",
        "guard", "veteran", "cleric",
    ])
    def test_role_no_trade(self, role):
        assert role not in trade.TRADE_ROLES


# ============================================================
# 7. ЧТО КАКАЯ РОЛЬ ПРОДАЁТ
# ============================================================

class TestRoleSells:
    """§35: что каждая роль с торговлей продаёт Бурту."""

    def test_elder_sells(self):
        items = trade.ROLE_SELLS["elder"]
        assert "bedroll" in items
        assert "waterskin" in items

    def test_blacksmith_sells(self):
        items = trade.ROLE_SELLS["blacksmith"]
        assert "club" in items
        assert "spear" in items
        assert "low_quality_sword" in items
        assert "ordinary_sword" in items
        assert "high_quality_sword" in items

    def test_trader_sells_everything(self):
        items = trade.ROLE_SELLS["merchant"]
        for name in trade.BASE_PRICES:
            assert name in items

    def test_fisher_sells(self):
        items = trade.ROLE_SELLS["fisherman"]
        assert "fish" in items
        assert "dried_fish" in items

    def test_tavernkeeper_sells(self):
        items = trade.ROLE_SELLS["tavernkeeper"]
        assert "bread" in items
        assert "waterskin" in items
        assert "tavern_room" in items

    def test_mage_sells_only_staff(self):
        items = trade.ROLE_SELLS["mage"]
        assert items == frozenset({"staff"})

    def test_warlock_sells_only_staff(self):
        items = trade.ROLE_SELLS["necromancer"]
        assert items == frozenset({"staff"})

    def test_every_trade_role_in_role_sells(self):
        for role in trade.TRADE_ROLES:
            assert role in trade.ROLE_SELLS

    def test_all_sold_items_are_buyable(self):
        # Что роль продаёт — то Бурт может купить (есть в BASE_PRICES)
        for role, items in trade.ROLE_SELLS.items():
            for name in items:
                assert name in trade.BASE_PRICES, (
                    f"роль {role} продаёт {name}, "
                    f"но его нет в BASE_PRICES"
                )
