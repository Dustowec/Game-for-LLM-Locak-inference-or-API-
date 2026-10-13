"""Тесты для burt/trade.py — §35 «Матрица торговли».

Формулы:
  модификатор локации (один раз при входе, живёт до конца сессии):
      1-2 -> +25%  (x1.25)
      3-4 ->  0%   (x1.00)
      5-6 -> -25%  (x0.75)
  покупка Буртом:  floor(base * mod)
  продажа Буртом:  floor(floor(base * 0.5) * mod)

Все цены — в МЕДЯКАХ (1 сер. = 10 мед., 1 зол. = 100 мед.).
Округление ВНИЗ на каждом шаге.

Роли с торговлей (7):  староста, кузнец, торговец, рыбак,
                       трактирщик, маг, чернокнижник
Роли без торговли (6): крестьянин, крестьянка, ребёнок,
                       стражник, ветеран, служитель
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
        assert trade.BASE_PRICES["хлеб"] == 2

    def test_fish(self):
        assert trade.BASE_PRICES["рыба"] == 2

    def test_dried_fish(self):
        assert trade.BASE_PRICES["вяленая рыба"] == 3

    def test_water_flask_small(self):
        # 2 мед.
        assert trade.BASE_PRICES["фляга с водой"] == 2

    def test_water_flask_big(self):
        # 1 сер. = 10 мед.
        assert trade.BASE_PRICES["фляга с водой большая"] == 10

    def test_sleeping_bag(self):
        assert trade.BASE_PRICES["спальный мешок"] == 5

    def test_tavern_room(self):
        assert trade.BASE_PRICES["комната в таверне"] == 5

    def test_club(self):
        # 1 сер. = 10 мед.
        assert trade.BASE_PRICES["дубина"] == 10

    def test_spear(self):
        # 2 сер. = 20 мед.
        assert trade.BASE_PRICES["копьё"] == 20

    def test_sword_low(self):
        # 1 сер. = 10 мед.
        assert trade.BASE_PRICES["меч низкого качества"] == 10

    def test_sword_normal(self):
        # 3 сер. = 30 мед.
        assert trade.BASE_PRICES["меч обычный"] == 30

    def test_sword_high(self):
        # 6 сер. = 60 мед.
        assert trade.BASE_PRICES["меч высокого качества"] == 60

    def test_staff(self):
        # 1 зол. = 100 мед.
        assert trade.BASE_PRICES["посох"] == 100


# ============================================================
# 3. ЦЕНЫ ЛУТА — ЧТО БУРТ ПРОДАЁТ
# ============================================================

class TestLootPrices:
    """§35: цены лута в медяках (база для продажи)."""

    def test_goblin_dagger(self):
        assert trade.LOOT_PRICES["кинжал гоблина"] == 3

    def test_goblin_staff(self):
        assert trade.LOOT_PRICES["колдовской посох гоблина"] == 6

    def test_bandage(self):
        assert trade.LOOT_PRICES["повязка"] == 1

    def test_fangs(self):
        # «клыки (2 шт.)» — 3 мед. за пару
        assert trade.LOOT_PRICES["клыки"] == 3

    def test_pelt(self):
        # 1 сер. = 10 мед.
        assert trade.LOOT_PRICES["шкура"] == 10

    def test_dragon_scale(self):
        # 10 зол. = 1000 мед.
        assert trade.LOOT_PRICES["чешуя дракона"] == 1000

    def test_dragon_fangs(self):
        # 5 зол. = 500 мед.
        assert trade.LOOT_PRICES["драконьи клыки"] == 500

    def test_dragon_bone(self):
        # 10 зол. = 1000 мед.
        assert trade.LOOT_PRICES["кость дракона"] == 1000


# ============================================================
# 4. ЦЕНА ПОКУПКИ
# ============================================================

class TestBuyPrice:
    """buy_price(base, mod) = floor(base * mod)."""

    def test_bread_base(self):
        assert trade.buy_price("хлеб", 1.0) == 2

    def test_bread_plus_25(self):
        # 2 * 1.25 = 2.5 -> 2
        assert trade.buy_price("хлеб", 1.25) == 2

    def test_bread_minus_25(self):
        # 2 * 0.75 = 1.5 -> 1
        assert trade.buy_price("хлеб", 0.75) == 1

    def test_sword_normal_base(self):
        assert trade.buy_price("меч обычный", 1.0) == 30

    def test_sword_normal_plus_25(self):
        # 30 * 1.25 = 37.5 -> 37
        assert trade.buy_price("меч обычный", 1.25) == 37

    def test_sword_normal_minus_25(self):
        # 30 * 0.75 = 22.5 -> 22
        assert trade.buy_price("меч обычный", 0.75) == 22

    def test_staff_plus_25(self):
        # 100 * 1.25 = 125
        assert trade.buy_price("посох", 1.25) == 125

    def test_rounds_down_always(self):
        # 3 * 1.25 = 3.75 -> 3, не 4
        assert trade.buy_price("вяленая рыба", 1.25) == 3

    def test_unknown_item_raises(self):
        with pytest.raises(KeyError):
            trade.buy_price("нет такого предмета", 1.0)

    def test_loot_not_buyable(self):
        # кинжал гоблина — лут, Бурт его НЕ покупает
        with pytest.raises(KeyError):
            trade.buy_price("кинжал гоблина", 1.0)


# ============================================================
# 5. ЦЕНА ПРОДАЖИ
# ============================================================

class TestSellPrice:
    """sell_price(base, mod) = floor(floor(base * 0.5) * mod)."""

    def test_bread_sell_base(self):
        # floor(floor(2 * 0.5) * 1.0) = floor(1 * 1) = 1
        assert trade.sell_price("хлеб", 1.0) == 1

    def test_sword_normal_sell_base(self):
        # floor(floor(30 * 0.5) * 1.0) = floor(15 * 1) = 15
        assert trade.sell_price("меч обычный", 1.0) == 15

    def test_sword_normal_sell_plus(self):
        # floor(15 * 1.25) = floor(18.75) = 18
        assert trade.sell_price("меч обычный", 1.25) == 18

    def test_sword_normal_sell_minus(self):
        # floor(15 * 0.75) = floor(11.25) = 11
        assert trade.sell_price("меч обычный", 0.75) == 11

    def test_goblin_dagger_sell_base(self):
        # floor(floor(3 * 0.5) * 1.0) = floor(1 * 1) = 1
        assert trade.sell_price("кинжал гоблина", 1.0) == 1

    def test_goblin_dagger_sell_plus(self):
        # floor(1 * 1.25) = 1
        assert trade.sell_price("кинжал гоблина", 1.25) == 1

    def test_goblin_dagger_sell_minus(self):
        # floor(1 * 0.75) = 0
        assert trade.sell_price("кинжал гоблина", 0.75) == 0

    def test_bandage_always_zero(self):
        # floor(floor(1 * 0.5) * mod) = 0 всегда
        # повязка за 1 мед. в продаже уходит за 0
        assert trade.sell_price("повязка", 1.0) == 0
        assert trade.sell_price("повязка", 1.25) == 0
        assert trade.sell_price("повязка", 0.75) == 0

    def test_dragon_scale_sell_base(self):
        # floor(floor(1000 * 0.5) * 1.0) = 500
        assert trade.sell_price("чешуя дракона", 1.0) == 500

    def test_dragon_scale_sell_plus(self):
        # floor(500 * 1.25) = 625
        assert trade.sell_price("чешуя дракона", 1.25) == 625

    def test_pelt_sell_base(self):
        # floor(floor(10 * 0.5) * 1.0) = 5
        assert trade.sell_price("шкура", 1.0) == 5

    def test_unknown_item_raises(self):
        with pytest.raises(KeyError):
            trade.sell_price("нет такого предмета", 1.0)

    def test_loot_sellable(self):
        assert trade.sell_price("колдовской посох гоблина", 1.0) == 3

    def test_regular_item_sellable(self):
        # Бурт может продать обратно хлеб
        assert trade.sell_price("хлеб", 1.0) == 1


# ============================================================
# 6. РОЛИ С ТОРГОВЛЕЙ И БЕЗ
# ============================================================

class TestTradeRoles:
    """§35: 7 ролей с торговлей, 6 без."""

    def test_count_with_trade(self):
        assert len(trade.TRADE_ROLES) == 7

    @pytest.mark.parametrize("role", [
        "староста", "кузнец", "торговец", "рыбак",
        "трактирщик", "маг", "чернокнижник",
    ])
    def test_role_has_trade(self, role):
        assert role in trade.TRADE_ROLES

    @pytest.mark.parametrize("role", [
        "крестьянин", "крестьянка", "ребёнок",
        "стражник", "ветеран", "служитель",
    ])
    def test_role_no_trade(self, role):
        assert role not in trade.TRADE_ROLES


# ============================================================
# 7. ЧТО КАКАЯ РОЛЬ ПРОДАЁТ
# ============================================================

class TestRoleSells:
    """§35: что каждая роль с торговлей продаёт Бурту."""

    def test_elder_sells(self):
        items = trade.ROLE_SELLS["староста"]
        assert "спальный мешок" in items
        assert "фляга с водой" in items

    def test_blacksmith_sells(self):
        items = trade.ROLE_SELLS["кузнец"]
        assert "дубина" in items
        assert "копьё" in items
        assert "меч низкого качества" in items
        assert "меч обычный" in items
        assert "меч высокого качества" in items

    def test_trader_sells_everything(self):
        items = trade.ROLE_SELLS["торговец"]
        for name in trade.BASE_PRICES:
            assert name in items

    def test_fisher_sells(self):
        items = trade.ROLE_SELLS["рыбак"]
        assert "рыба" in items
        assert "вяленая рыба" in items

    def test_tavernkeeper_sells(self):
        items = trade.ROLE_SELLS["трактирщик"]
        assert "хлеб" in items
        assert "фляга с водой" in items
        assert "комната в таверне" in items

    def test_mage_sells_only_staff(self):
        items = trade.ROLE_SELLS["маг"]
        assert items == frozenset({"посох"})

    def test_warlock_sells_only_staff(self):
        items = trade.ROLE_SELLS["чернокнижник"]
        assert items == frozenset({"посох"})

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