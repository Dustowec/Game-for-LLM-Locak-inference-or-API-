"""Тесты стыка loop.execute_action ↔ combat.resolve_round (§23, §26).

Проверяют, что в боевом режиме execute_action:
- собирает BurtStats из visible + hidden["spells"];
- восстанавливает CombatState из hidden["combat"];
- зовёт combat.resolve_round;
- пишет обратно hidden["combat"] (или очищает при завершении);
- синхронизирует visible.hp ↔ hidden.hp_raw ↔ combat.burt.hp;
- подмешивает format_combat_report в events, пока бой идёт;
- при завершении боя — переключает current_mode, не подмешивает [COMBAT].

format_sensory_report и его тесты не трогаются.
"""

import pytest

from burt import loop
from burt import combat as combat_mod
from burt.combat import CombatState, RoundResult, start_combat
from burt.bestiary import ENEMIES


# ─── хелперы ────────────────────────────────────────────────

def _any_enemy_key():
    return next(iter(ENEMIES))


def _rng_from(values):
    """rng, возвращающий значения по очереди; залипает на последнем.

    Пример: _rng_from([5]) -> всегда 5.
    Пример: _rng_from([2, 5]) -> 2, 5, 5, 5, ...
    """
    vals = list(values)
    if not vals:
        raise ValueError("_rng_from requires at least one value")
    box = {"i": 0}

    def _roll():
        i = box["i"]
        if i < len(vals):
            box["i"] = i + 1
            return vals[i]
        return vals[-1]

    return _roll


def _make_state(combat_dict, *, hp=10, hp_max=10, mp=3, mp_max=3,
                element=None, alignment=None):
    return {
        "meta": {"life": 1, "day": 1, "step": 0},
        "visible": {
            "hp": hp, "hp_max": hp_max, "mp": mp, "mp_max": mp_max,
            "eat": True, "sleep_counter": 0, "date": "1 day",
            "effects": [],
            "location": {"name": "X", "exits": []},
            "inventory": [],
            "wallet": {"gold": 0, "silver": 0, "copper": 0},
            "skills_visible": [],
            "state": "combat",
        },
        "hidden": {
            "hp_raw": hp, "mp_raw": mp,
            "current_mode": "combat",
            "combat": combat_dict,
            "spells": {"element": element, "alignment": alignment},
            "location_graph": {"n": {"north": None, "south": None,
                                     "east": None, "west": None}},
            "current_node_id": "n",
        },
    }


def _attack_action(enemy_id):
    return loop.Action(
        key=f"attack_{enemy_id}", label="Attack",
        target_id=enemy_id,
    )


def _state_with_one_enemy(key=None):
    key = key or _any_enemy_key()
    cs = start_combat([key], "burt")
    state = _make_state(cs.to_dict())
    return state, cs.enemies[0]


# ─── сборка BurtStats ──────────────────────────────────────

class TestBurtStatsAssembly:
    def _capture(self, monkeypatch):
        box = {}

        def fake_resolve(combat, burt, action, target_id, rng):
            box["combat"] = combat
            box["burt"] = burt
            box["action"] = action
            box["target_id"] = target_id
            box["rng"] = rng
            return RoundResult(combat=combat, burt=burt, outcome="ongoing")

        monkeypatch.setattr(loop, "combat", _Wrap(fake_resolve))
        return box

    def test_hp_mp_taken_from_visible(self, monkeypatch):
        box = self._capture(monkeypatch)
        state, e = _state_with_one_enemy()
        state["visible"]["hp"] = 7
        state["hidden"]["hp_raw"] = 7
        state["visible"]["mp"] = 2
        state["hidden"]["mp_raw"] = 2
        loop.execute_action(_attack_action(e.id), state, lambda: 5)
        assert box["burt"].hp == 7
        assert box["burt"].mp == 2

    def test_spells_false_when_no_element_no_alignment(self, monkeypatch):
        box = self._capture(monkeypatch)
        state, e = _state_with_one_enemy()
        loop.execute_action(_attack_action(e.id), state, lambda: 5)
        assert box["burt"].spells_available is False

    def test_spells_true_when_element_set(self, monkeypatch):
        box = self._capture(monkeypatch)
        state, e = _state_with_one_enemy()
        state["hidden"]["spells"]["element"] = "fire"
        loop.execute_action(_attack_action(e.id), state, lambda: 5)
        assert box["burt"].spells_available is True

    def test_spells_true_when_alignment_set(self, monkeypatch):
        box = self._capture(monkeypatch)
        state, e = _state_with_one_enemy()
        state["hidden"]["spells"]["alignment"] = "light"
        loop.execute_action(_attack_action(e.id), state, lambda: 5)
        assert box["burt"].spells_available is True


class _Wrap:
    """Заменяет модуль loop.combat на объект с одним resolve_round."""

    def __init__(self, resolve_round):
        self.resolve_round = resolve_round


# ─── атака ─────────────────────────────────────────────────

class TestAttack:
    def test_hit_reduces_enemy_hp(self):
        state, e = _state_with_one_enemy()
        hp_before = e.hp
        loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        assert state["hidden"]["combat"]["enemies"][0]["hp"] < hp_before

    def test_miss_does_not_reduce_enemy_hp(self):
        state, e = _state_with_one_enemy()
        hp_before = e.hp
        loop.execute_action(_attack_action(e.id), state, _rng_from([2]))
        assert state["hidden"]["combat"]["enemies"][0]["hp"] == hp_before

    def test_kill_ends_combat(self):
        state, e = _state_with_one_enemy()
        state["hidden"]["combat"]["enemies"][0]["hp"] = 1
        loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        assert state["hidden"]["combat"] is None
        assert state["hidden"]["current_mode"] == "exploring"

    def test_attack_missing_target_returns_error(self):
        state, _ = _state_with_one_enemy()
        result = loop.execute_action(
            _attack_action("no_such_enemy"), state, lambda: 5,
        )
        assert any("ошибка" in ev.lower() for ev in result.events)

    def test_attack_dead_target_returns_error(self):
        state, e = _state_with_one_enemy()
        state["hidden"]["combat"]["enemies"][0]["alive"] = False
        result = loop.execute_action(_attack_action(e.id), state, lambda: 5)
        assert any("ошибка" in ev.lower() for ev in result.events)


# ─── блок ──────────────────────────────────────────────────

class TestBlock:
    def test_block_adds_event(self):
        state, _ = _state_with_one_enemy()
        result = loop.execute_action(
            loop.Action(key="block", label="Block"), state, _rng_from([5]),
        )
        assert any("defensive" in ev.lower() or "block" in ev.lower() for ev in result.events)

    def test_block_combat_continues(self):
        state, _ = _state_with_one_enemy()
        loop.execute_action(
            loop.Action(key="block", label="Block"), state, _rng_from([5]),
        )
        assert state["hidden"]["combat"] is not None
        assert state["hidden"]["current_mode"] == "combat"


# ─── побег ─────────────────────────────────────────────────

class TestFlee:
    def test_flee_success_ends_combat(self):
        state, _ = _state_with_one_enemy()
        result = loop.execute_action(
            loop.Action(key="flee", label="Flee"), state, _rng_from([5]),
        )
        assert state["hidden"]["combat"] is None
        assert state["hidden"]["current_mode"] == "exploring"
        assert any("fled" in ev.lower() or "flee" in ev.lower() for ev in result.events)

    def test_flee_fail_keeps_combat(self):
        state, _ = _state_with_one_enemy()
        loop.execute_action(
            loop.Action(key="flee", label="Flee"), state, _rng_from([1, 1]),
        )
        assert state["hidden"]["combat"] is not None
        assert state["hidden"]["current_mode"] == "combat"

    def test_flee_from_no_flee_enemy_returns_error(self):
        keys = [
            k for k, e in ENEMIES.items()
            if e.tags and "no_flee" in e.tags
        ]
        if not keys:
            pytest.skip("no no_flee enemy in bestiary")
        state, _ = _state_with_one_enemy(keys[0])
        result = loop.execute_action(
            loop.Action(key="flee", label="Flee"), state, _rng_from([5]),
        )
        assert any("ошибка" in ev.lower() for ev in result.events)


# ─── смерть Бурта ──────────────────────────────────────────

class TestDeath:
    def test_burt_died_sets_game_over(self):
        state, e = _state_with_one_enemy()
        state["visible"]["hp"] = 1
        state["hidden"]["hp_raw"] = 1
        # Высокий урон от врага: две пятёрки — промах Бурта + удар врага.
        result = loop.execute_action(
            _attack_action(e.id), state, _rng_from([2, 5]),
        )
        assert result.game_over is True
        assert state["hidden"]["current_mode"] != "combat"
        assert state["hidden"]["combat"] is None


# ─── [COMBAT] в events ────────────────────────────────────────

class TestCombatReportInEvents:
    def test_ongoing_has_combat_report(self):
        state, e = _state_with_one_enemy()
        result = loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        joined = "\n".join(result.events)
        assert "[COMBAT]" in joined

    def test_finished_no_combat_report(self):
        state, e = _state_with_one_enemy()
        state["hidden"]["combat"]["enemies"][0]["hp"] = 1
        result = loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        joined = "\n".join(result.events)
        assert "[COMBAT]" not in joined


# ─── синхронизация состояния ───────────────────────────────

class TestStateSync:
    def test_visible_hp_synced_after_hit_from_enemy(self):
        state, e = _state_with_one_enemy()
        state["visible"]["hp"] = 10
        state["hidden"]["hp_raw"] = 10
        # rng: промах Бурта (2), удар врага (5).
        loop.execute_action(_attack_action(e.id), state, _rng_from([2, 5]))
        assert state["visible"]["hp"] == state["hidden"]["hp_raw"]
        assert state["visible"]["hp"] < 10

    def test_visible_state_does_not_leak_combat(self):
        state, e = _state_with_one_enemy()
        loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        assert "combat" not in state["visible"]

    def test_hidden_combat_is_dict_serializable(self):
        state, e = _state_with_one_enemy()
        loop.execute_action(_attack_action(e.id), state, _rng_from([5]))
        c = state["hidden"]["combat"]
        assert c is None or isinstance(c, dict)


# ─── меню боя ──────────────────────────────────────────────

class TestCombatMenu:
    def test_menu_reads_from_hidden_combat(self):
        state, e = _state_with_one_enemy()
        actions = loop.build_menu(state["visible"], state)
        keys = [a.key for a in actions]
        assert f"attack_{e.id}" in keys
        assert "block" in keys
        assert "flee" in keys

    def test_menu_no_attack_for_dead(self):
        state, e = _state_with_one_enemy()
        state["hidden"]["combat"]["enemies"][0]["alive"] = False
        actions = loop.build_menu(state["visible"], state)
        keys = [a.key for a in actions]
        assert f"attack_{e.id}" not in keys


# ─── ошибки ────────────────────────────────────────────────

class TestErrors:
    def test_no_combat_in_hidden_returns_error(self):
        state = _make_state(None)
        result = loop.execute_action(
            _attack_action("x"), state, lambda: 5,
        )
        assert any("ошибка" in ev.lower() for ev in result.events)

    def test_unknown_action_in_combat_returns_error(self):
        state, _ = _state_with_one_enemy()
        result = loop.execute_action(
            loop.Action(key="teleport", label="TP"), state, lambda: 5,
        )
        assert any("ошибка" in ev.lower() for ev in result.events)


# ─── rng по умолчанию ──────────────────────────────────────

class TestDefaultRng:
    def test_execute_action_works_without_rng(self):
        state, e = _state_with_one_enemy()
        # Просто проверяем, что не падает и меняет hidden.
        result = loop.execute_action(_attack_action(e.id), state)
        assert isinstance(result, loop.ActionResult)