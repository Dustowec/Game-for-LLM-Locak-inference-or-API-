"""Конфигурация pytest для проекта BURT.

Добавляет корень проекта в sys.path, чтобы тесты могли
импортировать пакет burt без установки проекта.

Это стандартный способ для src-layout и flat-layout проектов,
где pytest не запускается через `python -m pytest`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))