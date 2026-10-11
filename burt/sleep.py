"""
Сон — §5 ТЗ v0.7.0.

Сон:
  - доступен с шага 19, только при (спальный мешок ИЛИ комната) и вне боя;
  - на шаге 20, если модель не выбрала сон — принудительный;
  - сон = новый день: wrap → step 0, day+1 (оркестратор);
  - при любом сне: HP/MP = max, эффекты сняты (все, без исключений);
  - дневник: выбрала спать → пишет Бурт, иначе → пишет МИР.

Чистое ядро: без I/O, без asyncio, без LLM.
"""

from __future__ import annotations

# ─── Константы §5 ──────────────────────────────────────────

TIRED_AT: tuple[int, ...] = (19, 20)
SLEEP_AVAILABLE_FROM: int = 19
SLEEP_FORCED_AT: int = 20

DIARY_SOURCE_BURT: str = "burt"
DIARY_SOURCE_WORLD: str = "world"


# ─── Инжект «ты устал» / «ты сильно устал» ─────────────────

def should_inject_tired(step: int) -> bool:
    """
    Нужно ли в этом ходу добавить инжект усталости.

    Шаг 19 — «ты устал».
    Шаг 20 — «ты сильно устал».

    Разница в тексте собирается сенсорикой. Ядро сообщает только
    факт: инжект есть или нет.
    """
    return step in TIRED_AT


# ─── Доступность сна ───────────────────────────────────────

def is_sleep_available(
    step: int,
    in_combat: bool,
    has_bedroll: bool,
    has_room: bool,
) -> bool:
    """
    Доступен ли пункт «спать» в меню.

    Условия:
      - не в бою;
      - шаг >= 19;
      - есть спальный мешок ИЛИ куплена комната в таверне.
    """
    if in_combat:
        return False
    if step < SLEEP_AVAILABLE_FROM:
        return False
    return has_bedroll or has_room


# ─── Принудительный сон ────────────────────────────────────

def is_forced_sleep(step: int, chose_sleep: bool) -> bool:
    """
    Принудительный ли это сон.

    Шаг 20 и модель не выбрала сон → принудительный.
    На шаге 19 сон только добровольный: не выбрала — идём дальше.
    """
    if step != SLEEP_FORCED_AT:
        return False
    return not chose_sleep


# ─── Источник дневника ─────────────────────────────────────

def diary_source(chose_sleep: bool) -> str:
    """
    Кто пишет дневник.

    Выбрала спать → «burt».
    Иначе (в т.ч. принудительный) → «world».
    """
    if chose_sleep:
        return DIARY_SOURCE_BURT
    return DIARY_SOURCE_WORLD


# ─── Применение сна ────────────────────────────────────────

def apply_sleep(hp_max: int, mp_max: int) -> tuple[int, int, list]:
    """
    Применить эффекты сна.

    HP/MP восстанавливаются до максимума, все эффекты снимаются
    (благословение, проклятие — без исключений).

    Уровень, инвентарь, кошелёк, навыки, квесты — сохраняются,
    но это не зона sleep.py.

    Wrap дня (step → 0, day+1) и сброс флагов голода — оркестратор.

    Возвращает (hp, mp, effects).
    """
    return hp_max, mp_max, []