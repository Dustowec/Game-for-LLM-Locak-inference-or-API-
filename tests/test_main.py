"""Tests for main.py — entry point smoke tests."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

import main
from burt import state_io


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
        # roll=1 -> final death (roll != 6)
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