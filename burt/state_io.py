"""Файловые операции state.json — §30 ТЗ v0.7.0.

Атомарная запись через temp+replace. UTF-8 без ASCII escape.
load_state валидирует через validate_state.

Соглашения:
- save_state(path, state) — атомарно записать, создав каталог.
- load_state(path) — прочитать + validate_state.
- state_exists(path) — bool.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from burt.state import validate_state


def state_exists(path: Path | str) -> bool:
    """Есть ли файл по указанному пути."""
    return Path(path).is_file()


def save_state(path: Path | str, state: dict[str, Any]) -> None:
    """Атомарная запись state.json.

    Порядок:
    1. Валидация до любой записи на диск.
    2. Запись во временный файл.
    3. Замена целевого файла через os.replace (атомарно на одной ФС).

    При ошибке валидации существующий файл не трогается.
    Временный файл удаляется при любой ошибке.
    """
    target = Path(path)

    # Валидация ДО открытия файлов.
    # Так мусор не попадает на диск даже временно.
    validate_state(state)

    target.parent.mkdir(parents=True, exist_ok=True)

    # Временный файл рядом с целевым — гарантирует одну ФС
    # и атомарность os.replace.
    fd, tmp_name = tempfile.mkstemp(
        prefix=target.name + ".",
        suffix=".tmp",
        dir=str(target.parent),
    )
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                state,
                f,
                ensure_ascii=False,
                indent=2,
                sort_keys=False,
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, target)
    except BaseException:
        # Убираем за собой, если что-то пошло не так
        # до или во время os.replace.
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def load_state(path: Path | str) -> dict[str, Any]:
    """Читает state.json и валидирует.

    Raise:
    - FileNotFoundError, если файла нет.
    - ValueError, если JSON битый или state невалиден.
    """
    target = Path(path)

    if not target.is_file():
        raise FileNotFoundError(f"state file not found: {target}")

    raw = target.read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in {target}: {exc.msg} at line {exc.lineno}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"state root must be dict, got {type(data).__name__}"
        )

    validate_state(data)
    return data