"""Tests for burt/replicas.py — §2, §12, §32."""
import json
import logging
from pathlib import Path

import pytest

from burt import replicas


@pytest.fixture
def minimal_data():
    return {
        "roles": {
            "test_role": {
                "intro": ["hello 1", "hello 2"],
                "fail_angry": ["angry"],
                "fail": ["no"],
                "neutral": ["maybe"],
                "success": ["yes"],
                "success_bonus": ["bonus"],
                "trade_success": ["trade"],
            },
        },
        "events": {
            "test_event": {
                "intro": ["hello"],
                "fail_angry": ["angry"],
                "fail": ["no"],
                "neutral": ["maybe"],
                "success": ["yes"],
                "success_bonus": ["bonus"],
            },
        },
    }


@pytest.fixture
def data_path(tmp_path, minimal_data):
    p = tmp_path / "replicas.json"
    p.write_text(json.dumps(minimal_data, ensure_ascii=False), encoding="utf-8")
    return str(p)


@pytest.fixture(scope="module")
def real_path():
    return Path(__file__).parent.parent / "replicas.json"


@pytest.fixture(scope="module")
def real_data(real_path):
    return replicas.load_replicas(str(real_path))


class TestConstants:
    def test_required_role_sections(self):
        assert replicas.REQUIRED_ROLE_SECTIONS == frozenset({
            "intro", "fail_angry", "fail", "neutral",
            "success", "success_bonus",
        })

    def test_required_event_sections(self):
        assert replicas.REQUIRED_EVENT_SECTIONS == frozenset({"intro"})


class TestLoadReplicas:
    def test_loads_valid_file(self, data_path, minimal_data):
        assert replicas.load_replicas(data_path) == minimal_data

    def test_returns_dict(self, data_path):
        assert isinstance(replicas.load_replicas(data_path), dict)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            replicas.load_replicas(str(tmp_path / "missing.json"))

    def test_broken_json_raises(self, tmp_path):
        p = tmp_path / "broken.json"
        p.write_text("{ not json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            replicas.load_replicas(str(p))


class TestValidateReplicas:
    def test_valid_data_no_warns(self, minimal_data):
        assert replicas.validate_replicas(minimal_data) == []

    def test_missing_role_section(self, minimal_data):
        del minimal_data["roles"]["test_role"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "test_role" in warns[0]
        assert "intro" in warns[0]

    def test_missing_event_section(self, minimal_data):
        del minimal_data["events"]["test_event"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "test_event" in warns[0]
        assert "intro" in warns[0]

    def test_missing_optional_section_ok(self, minimal_data):
        del minimal_data["roles"]["test_role"]["trade_success"]
        assert replicas.validate_replicas(minimal_data) == []

    def test_empty_required_section_warns(self, minimal_data):
        minimal_data["roles"]["test_role"]["intro"] = []
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 1
        assert "intro" in warns[0]

    def test_multiple_problems(self, minimal_data):
        del minimal_data["roles"]["test_role"]["intro"]
        del minimal_data["events"]["test_event"]["intro"]
        warns = replicas.validate_replicas(minimal_data)
        assert len(warns) == 2

    def test_not_a_dict_raises(self):
        with pytest.raises(ValueError):
            replicas.validate_replicas(["not", "a", "dict"])

    def test_missing_roles_bucket(self, minimal_data):
        del minimal_data["roles"]
        warns = replicas.validate_replicas(minimal_data)
        assert any("roles" in w for w in warns)

    def test_missing_events_bucket(self, minimal_data):
        del minimal_data["events"]
        warns = replicas.validate_replicas(minimal_data)
        assert any("events" in w for w in warns)


class TestGetLine:
    def test_role_intro_first(self, minimal_data):
        rng = lambda seq: seq[0]
        assert replicas.get_line(
            minimal_data, "roles", "test_role", "intro", rng,
        ) == "hello 1"

    def test_role_intro_second(self, minimal_data):
        rng = lambda seq: seq[1]
        assert replicas.get_line(
            minimal_data, "roles", "test_role", "intro", rng,
        ) == "hello 2"

    def test_event_intro(self, minimal_data):
        rng = lambda seq: seq[0]
        assert replicas.get_line(
            minimal_data, "events", "test_event", "intro", rng,
        ) == "hello"

    def test_rng_called_with_sequence(self, minimal_data):
        received = []

        def rng(seq):
            received.append(list(seq))
            return seq[0]

        replicas.get_line(minimal_data, "roles", "test_role", "intro", rng)
        assert received == [["hello 1", "hello 2"]]

    def test_missing_section_returns_empty(self, minimal_data, caplog):
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "test_role", "trade_fail", rng,
            )
        assert line == ""
        assert any("trade_fail" in rec.message for rec in caplog.records)

    def test_unknown_role_returns_empty(self, minimal_data, caplog):
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "no_such", "intro", rng,
            )
        assert line == ""
        assert any("no_such" in rec.message for rec in caplog.records)

    def test_empty_section_returns_empty(self, minimal_data, caplog):
        minimal_data["roles"]["test_role"]["trade_success"] = []
        rng = lambda seq: seq[0]
        with caplog.at_level(logging.WARNING):
            line = replicas.get_line(
                minimal_data, "roles", "test_role", "trade_success", rng,
            )
        assert line == ""
        assert any("trade_success" in rec.message for rec in caplog.records)

    def test_invalid_kind_raises(self, minimal_data):
        rng = lambda seq: seq[0]
        with pytest.raises(ValueError):
            replicas.get_line(
                minimal_data, "not_roles", "test_role", "intro", rng,
            )


class TestRealReplicasFile:
    def test_file_exists(self, real_path):
        assert real_path.exists(), f"replicas.json not found: {real_path}"

    def test_no_warns(self, real_data):
        assert replicas.validate_replicas(real_data) == []

    def test_has_12_roles(self, real_data):
        assert len(real_data["roles"]) == 12

    def test_has_2_events(self, real_data):
        assert len(real_data["events"]) == 2

    def test_role_names(self, real_data):
        expected = {
            "elder", "peasant", "peasant_woman", "blacksmith",
            "merchant", "guard", "fisherman", "child",
            "veteran", "cleric", "necromancer", "tavernkeeper",
        }
        assert set(real_data["roles"].keys()) == expected

    def test_event_names(self, real_data):
        expected = {"mage_event", "preacher_event"}
        assert set(real_data["events"].keys()) == expected

    def test_all_roles_have_required(self, real_data):
        for name, role in real_data["roles"].items():
            for section in replicas.REQUIRED_ROLE_SECTIONS:
                assert section in role, f"{name}: no section {section}"
                assert len(role[section]) > 0, f"{name}: section {section} empty"

    def test_all_events_have_intro(self, real_data):
        for name, event in real_data["events"].items():
            assert "intro" in event, f"{name}: no intro"
            assert len(event["intro"]) > 0, f"{name}: intro empty"

    def test_all_sections_are_lists_of_nonempty_str(self, real_data):
        for kind in ("roles", "events"):
            for name, entry in real_data[kind].items():
                for section, lines in entry.items():
                    assert isinstance(lines, list), f"{name}.{section}: not a list"
                    for line in lines:
                        assert isinstance(line, str), f"{name}.{section}: not str"
                        assert line.strip() != "", f"{name}.{section}: empty"

    def test_prophet_has_own_sections(self, real_data):
        prophet = real_data["events"]["preacher_event"]
        assert "curse" in prophet
        assert "nothing" in prophet
        assert "blessing" in prophet

    def test_mage_has_train_sections(self, real_data):
        mage = real_data["events"]["mage_event"]
        assert "train_offer" in mage
        assert "train_done" in mage
        assert "train_locked" in mage

    def test_blacksmith_has_exit_early(self, real_data):
        smith = real_data["roles"]["blacksmith"]
        assert "exit_early" in smith

    def test_only_blacksmith_has_exit_early(self, real_data):
        for name, role in real_data["roles"].items():
            if name == "blacksmith":
                continue
            assert "exit_early" not in role, f"{name}: unexpected exit_early"
