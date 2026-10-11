"""Тесты для burt.state_io — файловые операции state.json §30.

TDD: атомарная запись temp+replace, UTF-8, round-trip.
Использует pytest tmp_path для изоляции.

Соглашения:
- save_state(path, state) — атомарная запись, создаёт каталог.
- load_state(path) — читает + validate_state, raise при ошибке.
- state_exists(path) — bool.
"""

import json
from pathlib import Path

import pytest

from burt.state import create_initial_state, validate_state
from burt.state_io import (
    load_state,
    save_state,
    state_exists,
)


# ---------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------

@pytest.fixture
def sample_state():
    return create_initial_state(
        life=1,
        session_uuid="test-session",
        config_hash="abc123",
        session_started="2026-10-11T20:00:00",
    )


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "state.json"


# ---------------------------------------------------------------------
# state_exists
# ---------------------------------------------------------------------

def test_state_exists_false_when_missing(state_path: Path):
    assert state_exists(state_path) is False


def test_state_exists_true_after_save(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    assert state_exists(state_path) is True


# ---------------------------------------------------------------------
# save_state + load_state — happy path
# ---------------------------------------------------------------------

def test_save_creates_file(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    assert state_path.exists()
    assert state_path.is_file()


def test_save_creates_parent_directories(tmp_path: Path, sample_state):
    nested = tmp_path / "a" / "b" / "c" / "state.json"
    save_state(nested, sample_state)
    assert nested.exists()


def test_round_trip_returns_equal_state(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert loaded == sample_state


def test_round_trip_preserves_russian_keys(state_path: Path, sample_state):
    """§30: репутация по ролям — русские ключи, UTF-8."""
    sample_state["hidden"]["reputation"]["кузнец"] = 5
    sample_state["hidden"]["reputation"]["чернокнижник"] = -3
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert loaded["hidden"]["reputation"]["кузнец"] == 5
    assert loaded["hidden"]["reputation"]["чернокнижник"] == -3


def test_round_trip_preserves_nested_structures(state_path: Path, sample_state):
    sample_state["visible"]["inventory"] = [
        {"name": "меч", "count": 1},
        {"name": "фляга с водой", "count": 1, "charges": 2, "charges_max": 2},
    ]
    sample_state["hidden"]["location_graph"]["node_start"]["north"] = "node_2"
    sample_state["hidden"]["location_graph"]["node_2"] = {
        "north": None, "south": "node_start", "east": None, "west": None,
    }
    sample_state["hidden"]["current_node_id"] = "node_2"
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert loaded["visible"]["inventory"][1]["charges"] == 2
    assert loaded["hidden"]["location_graph"]["node_start"]["north"] == "node_2"
    assert loaded["hidden"]["current_node_id"] == "node_2"


def test_round_trip_preserves_unicode_values(state_path: Path, sample_state):
    sample_state["visible"]["location"]["name"] = "Развилка у трёх дубов"
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert loaded["visible"]["location"]["name"] == "Развилка у трёх дубов"


def test_save_writes_utf8_no_ascii_escape(state_path: Path, sample_state):
    """Файл должен быть человекочитаемым, не \\uXXXX."""
    save_state(state_path, sample_state)
    raw = state_path.read_text(encoding="utf-8")
    assert "кузнец" in raw
    assert "\\u" not in raw


def test_save_produces_valid_json(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    with state_path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)
    assert "meta" in data


# ---------------------------------------------------------------------
# load_state — обработка ошибок
# ---------------------------------------------------------------------

def test_load_missing_file_raises(state_path: Path):
    with pytest.raises(FileNotFoundError):
        load_state(state_path)


def test_load_invalid_json_raises(state_path: Path):
    state_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_empty_file_raises(state_path: Path):
    state_path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_json_array_raises(state_path: Path):
    state_path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_invalid_state_raises(state_path: Path, sample_state):
    """Файл валидный JSON, но state не проходит validate_state."""
    sample_state["visible"]["hp"] = 9999
    # Пишем в обход save_state, чтобы валидация не сработала при записи
    state_path.write_text(
        json.dumps(sample_state, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_state(state_path)


def test_load_missing_required_section_raises(state_path: Path, sample_state):
    del sample_state["hidden"]
    state_path.write_text(
        json.dumps(sample_state, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_state(state_path)


# ---------------------------------------------------------------------
# save_state — валидация перед записью
# ---------------------------------------------------------------------

def test_save_rejects_invalid_state(state_path: Path, sample_state):
    """save_state не пишет мусор на диск."""
    sample_state["visible"]["hp"] = 9999
    with pytest.raises(ValueError):
        save_state(state_path, sample_state)
    assert not state_path.exists()


def test_save_does_not_touch_existing_file_on_invalid(
    state_path: Path, sample_state
):
    """Если новое состояние невалидно — старое остаётся нетронутым."""
    save_state(state_path, sample_state)
    original_bytes = state_path.read_bytes()

    bad_state = create_initial_state(
        life=2,
        session_uuid="other",
        config_hash="xyz",
        session_started="2026-10-12T00:00:00",
    )
    bad_state["visible"]["hp"] = 9999

    with pytest.raises(ValueError):
        save_state(state_path, bad_state)

    assert state_path.read_bytes() == original_bytes


# ---------------------------------------------------------------------
# Атомарность
# ---------------------------------------------------------------------

def test_save_does_not_leave_temp_file_on_success(
    state_path: Path, sample_state
):
    save_state(state_path, sample_state)
    siblings = list(state_path.parent.iterdir())
    assert siblings == [state_path]


def test_save_does_not_leave_temp_file_on_failure(
    state_path: Path, sample_state
):
    sample_state["visible"]["hp"] = 9999
    with pytest.raises(ValueError):
        save_state(state_path, sample_state)
    siblings = list(state_path.parent.iterdir())
    assert siblings == []


def test_save_overwrites_existing(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    sample_state["meta"]["day"] = 5
    sample_state["visible"]["hp"] = 7
    sample_state["hidden"]["hp_raw"] = 7
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert loaded["meta"]["day"] == 5
    assert loaded["visible"]["hp"] == 7


def test_save_is_idempotent(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    first = state_path.read_bytes()
    save_state(state_path, sample_state)
    second = state_path.read_bytes()
    assert first == second


def test_load_does_not_mutate_state_on_disk(state_path: Path, sample_state):
    save_state(state_path, sample_state)
    before = state_path.read_bytes()
    loaded = load_state(state_path)
    loaded["visible"]["hp"] = 1
    after = state_path.read_bytes()
    assert before == after


# ---------------------------------------------------------------------
# validate_state вызывается внутри load_state
# ---------------------------------------------------------------------

def test_load_calls_validate_state(state_path: Path, sample_state):
    """Если между сохранением и загрузкой файл побили —
    load_state должен упасть, а не вернуть битые данные."""
    save_state(state_path, sample_state)
    # Ломаем: hp_raw != hp
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["hidden"]["hp_raw"] = 999
    state_path.write_text(
        json.dumps(data, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_state(state_path)


# ---------------------------------------------------------------------
# Относительные пути
# ---------------------------------------------------------------------

def test_save_and_load_with_relative_path(tmp_path, monkeypatch, sample_state):
    monkeypatch.chdir(tmp_path)
    save_state(Path("state.json"), sample_state)
    assert Path("state.json").exists()
    loaded = load_state(Path("state.json"))
    assert loaded == sample_state


# ---------------------------------------------------------------------
# Большой state (проверка, что ничего не режется)
# ---------------------------------------------------------------------

def test_large_state_round_trip(state_path: Path, sample_state):
    sample_state["visible"]["inventory"] = [
        {"name": f"item_{i}", "count": i} for i in range(200)
    ]
    save_state(state_path, sample_state)
    loaded = load_state(state_path)
    assert len(loaded["visible"]["inventory"]) == 200
    assert loaded["visible"]["inventory"][199]["count"] == 199