"""burt/replicas.py — §2, §12, §32.

Загрузчик replicas.json + мягкая валидация + доступ к репликам.

Структура файла:
    {
      "roles":  { имя: {секция: [строки]} },   # 12 ролей
      "events": { имя: {секция: [строки]} }    # 2 события
    }

Политика ошибок (согласовано 13.10.2026):
    - Файл не читается / битый JSON  -> исключение (ERROR)
    - data не словарь                -> ValueError (программная ошибка)
    - kind не 'roles' / 'events'     -> ValueError (программная ошибка)
    - Нет обязательной секции        -> WARN + пропуск (играем)
    - Нет необязательной секции      -> WARN + "" при запросе
    - Пустая секция                  -> WARN + ""
    - Нет роли / события             -> WARN + ""

Обязательные секции:
    у любой роли — REQUIRED_ROLE_SECTIONS
    у любого события — REQUIRED_EVENT_SECTIONS (только intro)

WARN пишется в logger модуля. Оркестратор потом сам решает,
поднимать ли это до уровня ERROR (см. §39).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ============================================================
# КОНСТАНТЫ
# ============================================================

REQUIRED_ROLE_SECTIONS: frozenset[str] = frozenset({
    "intro",
    "fail_angry",
    "fail",
    "neutral",
    "success",
    "success_bonus",
})

REQUIRED_EVENT_SECTIONS: frozenset[str] = frozenset({
    "intro",
})

_VALID_KINDS: frozenset[str] = frozenset({"roles", "events"})


# ============================================================
# ЗАГРУЗКА
# ============================================================

def load_replicas(path: str) -> dict:
    """Читает replicas.json.

    FileNotFoundError — файла нет.
    json.JSONDecodeError — файл не JSON или битый.

    Никакой валидации структуры здесь нет: за это отвечает
    validate_replicas(). Причина: загрузку можно использовать
    в тестах отдельно от валидации.
    """
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# ВАЛИДАЦИЯ
# ============================================================

def validate_replicas(data: Any) -> list[str]:
    """Проверяет структуру. Возвращает список WARN-сообщений.

    Пустой список = всё ок.

    Не падает на дырах в данных: возвращает тексты для лога.
    Падает только на «программист передал не то» (ValueError).
    """
    if not isinstance(data, dict):
        raise ValueError(
            f"validate_replicas: ожидался dict, получено "
            f"{type(data).__name__}"
        )

    warns: list[str] = []

    warns.extend(_validate_bucket(data, "roles", REQUIRED_ROLE_SECTIONS))
    warns.extend(_validate_bucket(data, "events", REQUIRED_EVENT_SECTIONS))

    return warns


def _validate_bucket(
    data: dict,
    kind: str,
    required: frozenset[str],
) -> list[str]:
    """Проверяет одну секцию (roles или events)."""
    warns: list[str] = []

    if kind not in data:
        warns.append(f"replicas: нет секции {kind!r}")
        return warns

    bucket = data[kind]
    if not isinstance(bucket, dict):
        warns.append(
            f"replicas: секция {kind!r} не словарь "
            f"({type(bucket).__name__})"
        )
        return warns

    singular = "роль" if kind == "roles" else "событие"

    for name, entry in bucket.items():
        if not isinstance(entry, dict):
            warns.append(
                f"replicas: {singular} {name!r} не словарь "
                f"({type(entry).__name__})"
            )
            continue
        for section in required:
            if section not in entry:
                warns.append(
                    f"replicas: {singular} {name!r} — "
                    f"нет обязательной секции {section!r}"
                )
            elif not entry[section]:
                warns.append(
                    f"replicas: {singular} {name!r} — "
                    f"секция {section!r} пустая"
                )

    return warns


# ============================================================
# ПОЛУЧЕНИЕ РЕПЛИКИ
# ============================================================

def get_line(
    data: dict,
    kind: str,
    name: str,
    section: str,
    rng: Callable[[list[str]], str],
) -> str:
    """Возвращает случайную реплику из секции.

    data     — результат load_replicas.
    kind     — "roles" или "events".
    name     — имя роли / события.
    section  — имя секции (intro, fail_angry, trade_success, ...).
    rng      — функция, которая принимает список строк и возвращает
               одну строку. Обычно: lambda lines: random.choice(lines).

    Возвращает:
        - реплику (str), если всё есть;
        - "" + WARN, если роли/секции нет или она пустая.

    Кидает ValueError, если kind не из _VALID_KINDS — это баг
    вызывающего кода, не дыра в данных.
    """
    if kind not in _VALID_KINDS:
        raise ValueError(
            f"get_line: kind должен быть 'roles' или 'events', "
            f"получено {kind!r}"
        )

    singular = "роли" if kind == "roles" else "события"

    bucket = data.get(kind)
    if not isinstance(bucket, dict):
        logger.warning(
            "replicas: секция %r отсутствует или не словарь", kind,
        )
        return ""

    entry = bucket.get(name)
    if not isinstance(entry, dict):
        logger.warning(
            "replicas: нет %s %r", singular, name,
        )
        return ""

    lines = entry.get(section)
    if not lines:
        logger.warning(
            "replicas: у %s %r нет секции %r или она пуста",
            singular, name, section,
        )
        return ""

    return rng(lines)