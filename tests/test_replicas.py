"""Тесты для burt/replicas.py — §2, §12, §32.

Модуль работает с файлом replicas.json в корне проекта.

Структура файла (см. §32 + решение 13.10.2026):
    {
      "roles":  { "староста": {...}, ..., "трактирщик": {...} },   # 12
      "events": { "маг_событие": {...},
                  "проповедник_событие": {...} }                    # 2
    }

Политика ошибок (согласовано 13.10.2026):
    - Файл не читается / битый JSON  -> исключение (ERROR)
    - Нет ОБЯЗАТЕЛЬНОЙ секции        -> WARN, работаем
    - Нет НЕОБЯЗАТЕЛЬНОЙ секции      -> WARN + "" в момент запроса
    - Секция пустая                  -> WARN + ""
    - Невалидный kind у get_line     -> ValueError (программная ошибка)

Обязательные секции:
    у роли:   intro, fail_angry, fail, neutral, success, success_bonus
    у события: intro
    (у проповедника нет fail/neutral/success/success_bonus — это норма,
     у него curse/nothing/blessing)
"""
import json
import logging
from pathlib import Path

import pytest

from burt import replicas


# ============================================================
# ФИКСТУРЫ
# ============================================================

@pytest.fixture
def minimal_data():
    """Мини-версия для юнит-тестов."""
    return {
        "roles": {
            "тест_роль": {
                "intro": ["привет 1", "привет 2"],
                "fail_angry": ["зло"],
                "fail": ["нет"],
                "neutral": ["может"],
                "success": ["да"],
                "success_bonus": ["бонус"],
                "trade_success": ["торг"],
            },
        },
        "events": {
            "тест_событие": {
                "intro": ["привет"],
                "fail_angry": ["зло"],
                "fail": ["нет"],
                "neutral": ["может"],
                "success": ["да"],
                "success_bonus": ["бонус"],
            },
        },
    }


@pytest.fixture
def data_path(tmp_path, minimal_data):
    """Пишет minimal_data в файл."""
    p = tmp_path / "replicas.json"
    p.write_text(
        json.dumps(minimal_data, ensure_ascii=False),
        encoding="utf-8",
    )
    return str(p)


@pytest.fixture(scope="module")
def real_path():
    """Путь к настоящему replicas.json в корне проекта."""
    return Path(__file__).parent.parent / "replicas.json"


@pytest.fixture(scope="module")
def real_data(real_path):
    """Настоящий replicas.json, загруженный один раз на модуль."""
    return replicas.load_replicas(str(real_path))


# ============================================================
# КОНСТАНТЫ
# ============================================================

class TestConstants:
    def test_required_role_sections(self):
        assert replicas.REQUIRED_ROLE_SECTIONS == frozenset({
            "intro", "fail_angry", "fail", "neutral",
            "success", "success_bonus",
        })

    def test_required_event_sections(self):
        assert replicas.REQUIRED_EVENT_SECTIONS == frozenset({"intro"})


# ============================================================
# ЗАГРУЗКА
# ============================================================

class TestLoadReplicas:
    def test_loads_valid_file(self, data_path, minimal_data):
        loaded = replicas.load_replicas(data_path)
        assert loaded == minimal_data

    def test_returns_dict(self, data_path):
        loaded = replicas.load_replicas(data_path)
        assert isinstance(loaded, dict)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            replicas.load_replicas(str(tmp_path / "нет.json"))

    def test_broken_json_raises(self, tmp_path):
        p = tmp_path / "битый.json"
        p.write_text("{ это не json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            replicas.load_replicas(str(p))


# ============================================================
# ВАЛИДАЦИЯ
# ============================================================

class TestValidateReplicas:
    def test_valid_data_no_warns(self, minimal_data):
        assert replicas.validate_replicas(minimal_data) == []

    def test_missing_role_section(self, minimal_data):
        del minimal_data["roles"]["тест_роль"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "тест_роль" in warns[0]
        assert "intro" in warns[0]

    def test_missing_event_section(self, minimal_data):
        del minimal_data["events"]["тест_событие"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "тест_событие" in warns[0]
        assert "intro" in warns[0]

    def test_missing_optional_section_ok(self, minimal_data):
        # trade_success — необязательная
        del minimal_data["roles"]["тест_роль"]["trade_success"]
        assert replicas.validate_replicas(minimal_data) == []

    def test_empty_required_section_warns(self, minimal_data):
        minimal_data["roles"]["тест_роль"]["intro"] = []
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "intro" in warns[0]

    def test_multiple_problems(self, minimal_data):
        del minimal_data["roles"]["тест_роль"]["intro"]
        del minimal_data["events"]["тест_событие"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 2

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError):
            replicas.validate_replicas(["не", "словарь"])

    def test_missing_roles_bucket(self, minimal_data):
        del minimal_data["roles"]
        warns = replicas.validate_replicas(minimal_data)
        assert any("roles" in w for w in warns)

    def test_missing_events_bucket(self, minimal_data):
        del minimal_data["events"]
        warns = replicas.validate_replicas(minimal_data)
        assert any("events" in w for w in warns)


# ============================================================
# ПОЛУЧЕНИЕ РЕПЛИКИ
# ============================================================

class TestGetLine:
    def test_role_intro_first(self, minimal_data):
        rng = lambda seq: seq[0]
        line = replicas.get_line(
            minimal_data, "roles", "тест_роль", "intro", rng,
        )
        assert line == "привет 1"

    def test_role_intro_second(self, minimal_data):
        rng = lambda seq: seq[1]
        line = replicas.get_line(
            minimal_data, "roles", "тест_роль", "intro", rng,
        )
        assert line == "привет 2"

    def test_event_intro(self, minimal_data):
        rng = lambda seq: seq[0]
        line = replicas.get_line(
            minimal_data, "events", "тест_событие", "intro", rng,
        )
        assert line == "привет"

    def test_rng_called_with_sequence(self, minimal_data):
        received = []

        def rng(seq):
            received.append(list(seq))
            return seq[0]

        replicas.get_line(
            minimal_data, "roles", "тест_роль", "intro", rng,
        )
        assert received == [["привет 1", "привет 2"]]

    def test_missing_section_returns_empty(self, minimal_data, caplog):
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "тест_роль", "trade_fail", rng,
            )
        assert line == ""
        assert any(
            "trade_fail" in rec.message for rec in caplog.records
        )

    def test_unknown_role_returns_empty(self, minimal_data, caplog):
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "нет_такой", "intro", rng,
            )
        assert line == ""
        assert any(
            "нет_такой" in rec.message for rec in caplog.records
        )

    def test_empty_section_returns_empty(self, minimal_data, caplog):
        minimal_data["roles"]["тест_роль"]["trade_success"] = []
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "тест_роль",
                "trade_success", rng,
            )
        assert line == ""
        assert any(
            "trade_success" in rec.message for rec in caplog.records
        )

    def test_invalid_kind_raises(self, minimal_data):
        rng = lambda seq: seq[0]
        with pytest.raises(ValueError):
            replicas.get_line(
                minimal_data, "не_роли", "тест_роль", "intro", rng,
            )


# ============================================================
# РЕАЛЬНЫЙ ФАЙЛ
# ============================================================

class TestRealReplicasFile:
    def test_file_exists(self, real_path):
        assert real_path.exists(), (
            f"replicas.json не найден: {real_path}"
        )

    def test_no_warns(self, real_data):
        assert replicas.validate_replicas(real_data) == []

    def test_has_12_roles(self, real_data):
        assert len(real_data["roles"]) == 12

    def test_has_2_events(self, real_data):
        assert len(real_data["events"]) == 2

    def test_role_names(self, real_data):
        expected = {
            "староста", "крестьянин", "крестьянка", "кузнец",
            "торговец", "стражник", "рыбак", "ребёнок",
            "ветеран", "служитель_церкви", "чернокнижник",
            "трактирщик",
        }
        assert set(real_data["roles"].keys()) == expected

    def test_event_names(self, real_data):
        expected = {"маг_событие", "проповедник_событие"}
        assert set(real_data["events"].keys()) == expected

    def test_all_roles_have_required(self, real_data):
        for name, role in real_data["roles"].items():
            for section in replicas.REQUIRED_ROLE_SECTIONS:
                assert section in role, f"{name}: нет секции {section}"
                assert len(role[section]) > 0, (
                    f"{name}: секция {section} пустая"
                )

    def test_all_events_have_intro(self, real_data):
        for name, event in real_data["events"].items():
            assert "intro" in event, f"{name}: нет intro"
            assert len(event["intro"]) > 0, f"{name}: intro пустая"

    def test_all_sections_are_lists_of_nonempty_str(self, real_data):
        for kind in ("roles", "events"):
            for name, entry in real_data[kind].items():
                for section, lines in entry.items():
                    assert isinstance(lines, list), (
                        f"{name}.{section}: не список"
                    )
                    for line in lines:
                        assert isinstance(line, str), (
                            f"{name}.{section}: не строка: {line!r}"
                        )
                        assert line.strip() != "", (
                            f"{name}.{section}: пустая строка"
                        )

    def test_prophet_has_own_sections(self, real_data):
        # §13: проповедник — curse / nothing / blessing
        prophet = real_data["events"]["проповедник_событие"]
        assert "curse" in prophet
        assert "nothing" in prophet
        assert "blessing" in prophet

    def test_mage_has_train_sections(self, real_data):
        mage = real_data["events"]["маг_событие"]
        assert "train_offer" in mage
        assert "train_done" in mage
        assert "train_locked" in mage

    def test_blacksmith_has_exit_early(self, real_data):
        # §32: кузнец обидчив — есть exit_early
        smith = real_data["roles"]["кузнец"]
        assert "exit_early" in smith

    def test_only_blacksmith_has_exit_early(self, real_data):
        for name, role in real_data["roles"].items():
            if name == "кузнец":
                continue
            assert "exit_early" not in role, (
                f"{name}: неожиданная секция exit_early"
            )