"""Граф локаций §17.

Структура узла:
  {
    "type": str | None,      # тип локации; None = ещё не сгенерирован
    "entered": bool,         # Бурт уже входил сюда
    "exits": {               # всегда 4 ключа
      "north": str | None,   # id соседа или None
      "east":  str | None,
      "south": str | None,
      "west":  str | None,
    },
  }

Граф неориентированный: если A.north = B, то B.south = A.
Чистое ядро — без I/O, без asyncio, без LLM.
"""
from __future__ import annotations


# ---------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------

DIRECTIONS = ("north", "east", "south", "west")

OPPOSITE = {
    "north": "south",
    "south": "north",
    "east": "west",
    "west": "east",
}

START_NODE_ID = "start"

LOCATION_TYPES = frozenset({
    "старт", "кустарник",
    "лес", "поле", "степь", "болото", "река", "дорога", "деревня",
    "храм", "подземелье",
})

# Индексы в DIRECTIONS: north=0, east=1, south=2, west=3.
# Пары для roll_exit_directions при n=2.
_EXIT_PAIRS = (
    (0, 1),  # roll=1: north, east
    (0, 2),  # roll=2: north, south
    (0, 3),  # roll=3: north, west
    (1, 2),  # roll=4: east, south
    (1, 3),  # roll=5: east, west
    (2, 3),  # roll=6: south, west
)


def _check_d6(roll: int, name: str = "roll") -> None:
    if not isinstance(roll, int) or not (1 <= roll <= 6):
        raise ValueError(f"{name} must be 1..6, got {roll!r}")


# ---------------------------------------------------------------------
# Расклад типа локации
# ---------------------------------------------------------------------

def roll_location_type(roll: int, roll_size: int | None = None) -> str:
    """Тип локации по 1d6 (+ уточняющий бросок при roll=5 и roll=6).

    roll=1-2 → лес
    roll=3   → поле
    roll=4   → степь
    roll=5   → roll_size 1-3 → болото / река / дорога
    roll=6   → roll_size 1-6 → храм (1) / подземелье (2) / деревня (3-6)

    "старт" и "кустарник" здесь не выпадают никогда.
    """
    _check_d6(roll)

    if roll == 1 or roll == 2:
        return "лес"
    if roll == 3:
        return "поле"
    if roll == 4:
        return "степь"

    if roll == 5:
        if roll_size is None:
            raise ValueError("roll=5 requires roll_size (1..3)")
        if roll_size not in (1, 2, 3):
            raise ValueError(f"roll_size must be 1..3, got {roll_size!r}")
        return {1: "болото", 2: "река", 3: "дорога"}[roll_size]

    # roll == 6
    if roll_size is None:
        raise ValueError("roll=6 requires roll_size (1..6)")
    if not isinstance(roll_size, int) or not (1 <= roll_size <= 6):
        raise ValueError(f"roll_size must be 1..6, got {roll_size!r}")
    if roll_size == 1:
        return "храм"
    if roll_size == 2:
        return "подземелье"
    return "деревня"


# ---------------------------------------------------------------------
# Количество выходов и их направления
# ---------------------------------------------------------------------

def roll_exit_count(roll: int) -> int:
    """Сколько выходов у нового узла: 1-2 → 2, 3-4 → 3, 5-6 → 4."""
    _check_d6(roll)
    if roll <= 2:
        return 2
    if roll <= 4:
        return 3
    return 4


def roll_exit_directions(n: int, roll: int) -> tuple[str, ...]:
    """Какие направления получают выход.

    n=4 → все четыре (roll игнорируется).
    n=3 → исключается одно (по roll, с заворотом 5→1, 6→2).
    n=2 → выбирается пара (по roll).

    Порядок — как в DIRECTIONS.
    """
    if n not in (2, 3, 4):
        raise ValueError(f"n must be 2, 3 or 4, got {n!r}")
    _check_d6(roll)

    if n == 4:
        return DIRECTIONS

    if n == 3:
        excluded_idx = (roll - 1) % 4
        return tuple(
            d for i, d in enumerate(DIRECTIONS) if i != excluded_idx
        )

    # n == 2
    i, j = _EXIT_PAIRS[roll - 1]
    return (DIRECTIONS[i], DIRECTIONS[j])


# ---------------------------------------------------------------------
# Узлы и связывание
# ---------------------------------------------------------------------

def _empty_node(node_type: str | None = None,
                entered: bool = False) -> dict:
    return {
        "type": node_type,
        "entered": entered,
        "exits": {d: None for d in DIRECTIONS},
    }


def _fresh_id(graph: dict) -> str:
    """Свободный id вида node_N."""
    i = 1
    while f"node_{i}" in graph:
        i += 1
    return f"node_{i}"


def link(graph: dict, from_id: str, direction: str, to_id: str) -> None:
    """Связать два узла симметрично.

    graph[from_id].exits[direction] = to_id
    graph[to_id].exits[OPPOSITE[direction]] = from_id

    Оба слота должны быть свободны; иначе ValueError.
    """
    if direction not in DIRECTIONS:
        raise ValueError(f"invalid direction: {direction!r}")
    if from_id not in graph:
        raise KeyError(from_id)
    if to_id not in graph:
        raise KeyError(to_id)

    fwd = graph[from_id]["exits"]
    bwd = graph[to_id]["exits"]
    back = OPPOSITE[direction]

    if fwd[direction] is not None:
        raise ValueError(
            f"{from_id}.{direction} already linked to {fwd[direction]}"
        )
    if bwd[back] is not None:
        raise ValueError(
            f"{to_id}.{back} already linked to {bwd[back]}"
        )

    fwd[direction] = to_id
    bwd[back] = from_id


# ---------------------------------------------------------------------
# Стартовый граф
# ---------------------------------------------------------------------

def create_start_graph() -> dict:
    """Стартовый граф §37.

    Центр "start" с 4 соседями:
      north → дорога
      east  → кустарник
      south → лес
      west  → река

    У соседей только одно ребро — обратно на старт.
    """
    graph: dict = {}
    graph[START_NODE_ID] = _empty_node("старт", entered=True)

    preset = {
        "north": "дорога",
        "east": "кустарник",
        "south": "лес",
        "west": "река",
    }

    for d in DIRECTIONS:
        nid = _fresh_id(graph)
        graph[nid] = _empty_node(preset[d], entered=False)
        link(graph, START_NODE_ID, d, nid)

    return graph


# ---------------------------------------------------------------------
# Вход в узел
# ---------------------------------------------------------------------

def enter_node(graph: dict, node_id: str,
               roll_count: int,
               roll_dirs: int,
               roll_type: int | None = None,
               roll_size: int | None = None) -> None:
    """Войти в узел: заполнить тип (если пуст) и сгенерировать выходы.

    Шаги:
      1. Проверить, что узел ещё не entered.
      2. Если type=None — сгенерировать по roll_type (+ roll_size).
         Если type уже задан (стартовые соседи) — оставить как есть.
      3. entered = True.
      4. Сгенерировать выходы по roll_count/roll_dirs.
         Занятые направления (например, back-ребро) пропускаются.
    """
    if node_id not in graph:
        raise KeyError(node_id)

    node = graph[node_id]

    if node["entered"]:
        raise ValueError(f"node {node_id} already entered")

    if node["type"] is None:
        if roll_type is None:
            raise ValueError(
                f"node {node_id} has no type; roll_type required"
            )
        node["type"] = roll_location_type(roll_type, roll_size)

    node["entered"] = True

    exit_count = roll_exit_count(roll_count)
    target_dirs = roll_exit_directions(exit_count, roll_dirs)

    for d in target_dirs:
        if node["exits"][d] is not None:
            continue  # back-ребро или уже занято
        new_id = _fresh_id(graph)
        graph[new_id] = _empty_node()
        link(graph, node_id, d, new_id)