"""Tests for main.py — entry point smoke tests + П.2–П.5 contracts."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

import main
from burt import loop, state_io


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _fresh_state() -> dict:
    st = main.make_new_state(life=1)
    main._sync_hidden_from_meta(st)
    main._ensure_runtime_fields(st)
    return st


# ---------------------------------------------------------------------
# State creation
# ---------------------------------------------------------------------

class TestMakeNewState:
    def test_returns_dict(self):
        st = main.make_new_state()
        assert isinstance(st, dict)

    def test_has_required_sections(self):
        st = main.make_new_state()
        for s in ("meta", "visible", "hidden"):
            assert s in st

    def test_life_is_set(self):
        st = main.make_new_state(life=3)
        assert st["meta"]["life"] == 3


class TestEnsureRuntimeFields:
    def test_adds_resurrection_flag(self):
        st = _fresh_state()
        assert "resurrection_used_today" in st["hidden"]

    def test_adds_micro_location(self):
        st = _fresh_state()
        assert "micro_location" in st["hidden"]

    def test_keeps_existing_combat(self):
        st = _fresh_state()
        st["hidden"]["combat"] = {"fake": True}
        main._ensure_runtime_fields(st)
        assert st["hidden"]["combat"] == {"fake": True}


class TestSyncMetaFromHidden:
    def test_syncs_step(self):
        st = _fresh_state()
        st["hidden"]["step"] = 5
        main._sync_meta_from_hidden(st)
        assert st["meta"]["step"] == 5

    def test_syncs_day(self):
        st = _fresh_state()
        st["hidden"]["day"] = 3
        main._sync_meta_from_hidden(st)
        assert st["meta"]["day"] == 3

    def test_updates_date(self):
        st = _fresh_state()
        st["hidden"]["day"] = 4
        main._sync_meta_from_hidden(st)
        assert st["visible"]["date"] == "4 day"


class TestSaveLoadRoundtrip:
    def test_save_load_same(self, tmp_path):
        st = _fresh_state()
        main._sync_meta_from_hidden(st)
        p = tmp_path / "state.json"
        state_io.save_state(p, st)
        loaded = state_io.load_state(p)
        assert loaded["meta"]["life"] == st["meta"]["life"]
        assert loaded["visible"]["hp"] == st["visible"]["hp"]


# ---------------------------------------------------------------------
# Dry run — no LLM
# ---------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_one_turn(self, tmp_path, capsys):
        st = _fresh_state()
        main._sync_meta_from_hidden(st)
        p = tmp_path / "state.json"
        asyncio.run(main.game_loop(
            st, [], max_steps=1, dry_run=True, state_path=p,
        ))
        out = capsys.readouterr().out
        assert "[STATE]" in out
        assert "Menu:" in out


# ---------------------------------------------------------------------
# Hunger check
# ---------------------------------------------------------------------

class TestHungerCheck:
    def test_no_death_on_safe_step(self):
        st = _fresh_state()
        st["hidden"]["step"] = 5
        assert main._check_hunger_death(st, lambda: 1) == "no_death"

    def test_death_on_step_8_without_eat(self):
        st = _fresh_state()
        st["hidden"]["step"] = 8
        st["visible"]["eat"] = False
        st["hidden"]["resurrection_used_today"] = False
        assert main._check_hunger_death(st, lambda: 1) == "final_death"

    def test_resurrection_on_roll_6(self):
        st = _fresh_state()
        st["hidden"]["step"] = 8
        st["visible"]["eat"] = False
        st["hidden"]["resurrection_used_today"] = False
        assert main._check_hunger_death(st, lambda: 6) == "resurrected"

    def test_no_death_when_eat_true(self):
        st = _fresh_state()
        st["hidden"]["step"] = 8
        st["visible"]["eat"] = True
        assert main._check_hunger_death(st, lambda: 1) == "no_death"


# ---------------------------------------------------------------------
# Sleep
# ---------------------------------------------------------------------

class TestDoSleep:
    def test_sleep_restores_hp(self):
        st = _fresh_state()
        st["visible"]["hp"] = 1
        st["hidden"]["hp_raw"] = 1
        main._do_sleep(st)
        assert st["visible"]["hp"] == st["visible"]["hp_max"]

    def test_sleep_wraps_day(self):
        st = _fresh_state()
        st["hidden"]["day"] = 5
        st["hidden"]["step"] = 19
        main._do_sleep(st)
        assert st["hidden"]["day"] == 6
        assert st["hidden"]["step"] == 0

    def test_sleep_clears_effects(self):
        st = _fresh_state()
        st["visible"]["effects"] = ["blessed", "cursed"]
        main._do_sleep(st)
        assert st["visible"]["effects"] == []

    def test_sleep_resets_hunger(self):
        st = _fresh_state()
        st["visible"]["eat"] = True
        main._do_sleep(st)
        assert st["visible"]["eat"] is False


# ---------------------------------------------------------------------
# П.2: _determine_death_cause (pure helper)
# ---------------------------------------------------------------------

class TestDetermineDeathCause:
    """П.2: pure helper, no side effects."""

    def test_combat_attack(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        cause = main._determine_death_cause(
            st, loop.Action("attack_wolf_1", "Attack wolf"),
        )
        assert cause == "combat"

    def test_combat_block(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        cause = main._determine_death_cause(
            st, loop.Action("block", "Block"),
        )
        assert cause == "combat"

    def test_combat_flee(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        cause = main._determine_death_cause(
            st, loop.Action("flee", "Flee"),
        )
        assert cause == "combat"

    def test_osmotret_penalty(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        st["hidden"]["last_action"] = "osmotret"
        st["hidden"]["same_action_count"] = 3
        cause = main._determine_death_cause(
            st, loop.Action("osmotret", "Look around"),
        )
        assert cause == "osmotret_penalty"

    def test_god_wrath_micro_event(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        st["hidden"]["micro_location"] = {
            "active": True, "damage": 1, "event_type": "god_wrath",
        }
        cause = main._determine_death_cause(
            st, loop.Action("go_back", "Back"),
        )
        assert cause == "god_wrath"

    def test_stone_micro_event(self):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        st["hidden"]["micro_location"] = {
            "active": True, "damage": 3, "event_type": "stone",
        }
        cause = main._determine_death_cause(
            st, loop.Action("go_north", "Go north"),
        )
        assert cause == "stone"

    def test_hunger(self):
        """hp>0 (hunger doesn't zero HP) + non-combat action -> hunger."""
        st = _fresh_state()
        st["visible"]["hp"] = 5
        st["visible"]["eat"] = False
        st["hidden"]["step"] = 18
        cause = main._determine_death_cause(
            st, loop.Action("search", "Search"),
        )
        assert cause == "hunger"

    def test_unknown(self):
        """hp=0, no combat/micro/osmotret signal -> unknown."""
        st = _fresh_state()
        st["visible"]["hp"] = 0
        cause = main._determine_death_cause(
            st, loop.Action("search", "Search"),
        )
        assert cause == "unknown"


# ---------------------------------------------------------------------
# П.2: _log_death (WARNING with cause, step, day, hp, location)
# ---------------------------------------------------------------------

class TestLogDeath:
    def test_warning_contains_cause(self, caplog):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        st["hidden"]["step"] = 17
        st["hidden"]["day"] = 1
        st["hidden"]["last_action"] = "osmotret"
        st["hidden"]["same_action_count"] = 3
        action = loop.Action("osmotret", "Look around")

        with caplog.at_level(logging.WARNING):
            main._log_death(st, action)

        warns = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.WARNING]
        assert any("cause=osmotret_penalty" in m for m in warns), warns

    def test_warning_contains_step_day_hp_location(self, caplog):
        st = _fresh_state()
        st["visible"]["hp"] = 0
        st["visible"]["location"]["name"] = "Dungeon"
        st["hidden"]["step"] = 11
        st["hidden"]["day"] = 2
        st["hidden"]["micro_location"] = {
            "active": True, "damage": 1, "event_type": "god_wrath",
        }
        action = loop.Action("go_north", "Go north")

        with caplog.at_level(logging.WARNING):
            main._log_death(st, action)

        warns = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.WARNING]
        assert any(
            "step=11" in m and "day=2" in m and "hp=0" in m
            and "location=Dungeon" in m
            and "cause=god_wrath" in m
            for m in warns
        ), warns


# ---------------------------------------------------------------------
# П.3: _log_result_events (все на INFO)
# ---------------------------------------------------------------------

class TestLogResultEvents:
    def test_events_logged_at_info(self, caplog):
        result = loop.ActionResult(events=["event one", "event two"])
        with caplog.at_level(logging.INFO):
            main._log_result_events(result)
        infos = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.INFO]
        assert any("event one" in m for m in infos), infos
        assert any("event two" in m for m in infos), infos

    def test_state_event_at_info(self, caplog):
        result = loop.ActionResult(events=["[STATE]\nHP: 10/10"])
        with caplog.at_level(logging.INFO):
            main._log_result_events(result)
        infos = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.INFO]
        assert any("[STATE]" in m for m in infos), infos

    def test_combat_event_at_info(self, caplog):
        result = loop.ActionResult(events=["[COMBAT]\nEnemy: wolf"])
        with caplog.at_level(logging.INFO):
            main._log_result_events(result)
        infos = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.INFO]
        assert any("[COMBAT]" in m for m in infos), infos


# ---------------------------------------------------------------------
# П.4: _log_inject (header+menu INFO, full DEBUG)
# ---------------------------------------------------------------------

class TestLogInject:
    def _menu(self):
        return [
            loop.Action("osmotret", "Look around"),
            loop.Action("go_north", "Go north"),
        ]

    def test_header_info(self, caplog):
        with caplog.at_level(logging.INFO):
            main._log_inject(
                step=5, day=2, mode="exploring",
                menu=self._menu(), user_msg="payload",
            )
        infos = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.INFO]
        assert any(
            "inject" in m
            and "mode=exploring" in m
            and "step=5" in m
            and "day=2" in m
            and "actions=2" in m
            for m in infos
        ), infos

    def test_menu_listed_info(self, caplog):
        with caplog.at_level(logging.INFO):
            main._log_inject(
                step=0, day=1, mode="exploring",
                menu=self._menu(), user_msg="",
            )
        infos = [r.getMessage() for r in caplog.records
                 if r.levelno == logging.INFO]
        assert any(
            "0=osmotret" in m and "1=go_north" in m for m in infos
        ), infos

    def test_full_text_debug(self, caplog):
        user_msg = "[STATE]\nHP: 10/10\n\nMENU:\n0. Look around\n\nCHOICE:"
        with caplog.at_level(logging.DEBUG):
            main._log_inject(
                step=0, day=1, mode="exploring",
                menu=self._menu(), user_msg=user_msg,
            )
        debugs = [r.getMessage() for r in caplog.records
                  if r.levelno == logging.DEBUG]
        assert any(
            "[STATE]" in m and "MENU:" in m for m in debugs
        ), debugs


# ---------------------------------------------------------------------
# П.5: no truncation
# ---------------------------------------------------------------------

class TestNoTruncation:
    @pytest.mark.asyncio
    async def test_llm_answer_logged_full(self, caplog):
        """Answer must not be truncated to 200 chars."""
        st = _fresh_state()
        long_answer = "X" * 500 + "\nCHOICE: 0"

        async def fake_call(system_msg, user_msg, history=None):
            return long_answer, []

        with patch.object(main.llm_client, "call_llm", side_effect=fake_call):
            with caplog.at_level(logging.INFO):
                await main.run_turn(st, [], rng=lambda: 4, dry_run=False)

        llm_logs = [r.getMessage() for r in caplog.records
                    if "LLM:" in r.getMessage()]
        assert llm_logs, "LLM answer should be logged"
        max_len = max(len(m) for m in llm_logs)
        assert max_len > 300, (
            f"answer must NOT be truncated at 200; got max len {max_len}"
        )