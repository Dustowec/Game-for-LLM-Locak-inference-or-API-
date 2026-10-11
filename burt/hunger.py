"""
Голод — §4 ТЗ v0.7.0.

Жёсткий порог, не шкала. Счётчик не тикает.

Инжект «ты голоден»:
  - шаги 0 и 10 — обязательный, вне зависимости от eat;
  - остальные шаги — только при eat=False.

Смерть:
  - шаги 8 и 18 — если eat=False;
  - проверка на ВЫХОДЕ из хода (после действия модели);
  - бросок 1d6: 6 = воскрешение (2 HP), иначе окончательная смерть;
  - если рес уже использован сегодня — окончательная смерть без броска.

Еда:
  - eat=True, +1 HP, кап по hp_max;
  - MP не восстанавливает.

Сон:
  - eat=False, флаг реса сбрасывается (новый день = новая милость).

Чистое ядро: без I/O, без asyncio, без LLM.
"""

from __future__ import annotations

from enum import Enum

# ─── Константы §4 ──────────────────────────────────────────

HUNGER_HUNGRY_AT: tuple[int, ...] = (0, 10)
HUNGER_DEATH_AT: tuple[int, ...] = (8, 18)

RESURRECTION_HP: int = 2
FOOD_HEAL: int = 1


# ─── Исходы проверки голода ────────────────────────────────

class HungerOutcome(Enum):
    """Результат проверки голода на выходе из хода."""

    NO_DEATH = "no_death"
    RESURRECTED = "resurrected"
    FINAL_DEATH = "final_death"


# ─── Инжект «ты голоден» ───────────────────────────────────

def should_inject_hunger(step: int, eat: bool) -> bool:
    """
    Нужно ли в этом ходу добавить «ты голоден» в сенсорный отчёт.

    Шаги 0 и 10 — обязательный инжект (границы циклов).
    Остальные шаги — только при eat=False.
    """
    if step in HUNGER_HUNGRY_AT:
        return True
    return not eat


# ─── Проверка голода на выходе из хода ─────────────────────

def resolve_hunger(
    step: int,
    eat: bool,
    resurrection_used_today: bool,
    roll: int,
) -> HungerOutcome:
    """
    Проверка голода на ВЫХОДЕ из хода.

    step — текущий шаг дня (0..19).
    eat — флаг «сыт» после действия модели в этом ходу.
    resurrection_used_today — был ли уже рес сегодня.
    roll — результат 1d6. Игнорируется, если броска не требуется.

    Возвращает:
      NO_DEATH      — смерти нет (безопасный шаг или eat=True);
      RESURRECTED   — смерть, но кубик = 6, Бурт жив с 2 HP;
      FINAL_DEATH   — окончательная смерть.
    """
    if step not in HUNGER_DEATH_AT:
        return HungerOutcome.NO_DEATH

    if eat:
        return HungerOutcome.NO_DEATH

    if resurrection_used_today:
        return HungerOutcome.FINAL_DEATH

    if roll == 6:
        return HungerOutcome.RESURRECTED

    return HungerOutcome.FINAL_DEATH


# ─── Еда ───────────────────────────────────────────────────

def apply_eat(eat: bool, hp: int, hp_max: int) -> tuple[bool, int]:
    """
    Применить поедание еды.

    eat → True (голод снят).
    HP += 1, с капом по hp_max.
    MP не трогается.

    Возвращает (eat, hp).
    """
    new_hp = min(hp + FOOD_HEAL, hp_max)
    return True, new_hp


# ─── Сон ───────────────────────────────────────────────────

def reset_hunger_after_sleep() -> tuple[bool, bool]:
    """
    Сброс состояния голода после сна.

    Новый день = Бурт просыпается голодным (eat=False),
    возможность реса восстанавливается (новый день = новая милость).

    Возвращает (eat, resurrection_used_today).
    """
    return False, False