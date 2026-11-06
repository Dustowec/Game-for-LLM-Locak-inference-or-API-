"""Tests for burt/quests.py -- section 18, 33, 36 spec."""
import pytest

from burt.quests import (
    Quest,
    quest_can_give,
    quest_give,
    quest_progress,
    try_deceive,
    quest_complete,
    quest_fail,
    expire_blockades,
    expire_deceit_penalties,
    quest_get_active,
)


def make_state(day=1, node_id="start", mode="exploring"):
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": f"{day} day",
            "effects": [],
            "location": {"name": "Crossroads", "exits": ["north"]},
            "inventory": [{"name": "кинжал гоблина", "count": 20},
                          {"name": "посох гоблина", "count": 2}],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
            "quests_issued_today": {},
        },
        "hidden": {
            "current_mode": mode, "current_node_id": node_id,
            "day": day, "step": 0,
            "quests_raw": [],
            "role_quest_block": {},
            "quest_deceive_attempts": {},
            "deceit_penalty_until": {},
            "quests_issued_today": {},
            "killed_quest_givers": [],
            "reputation": {},
        },
    }


class TestQuestCreation:
    def test_quest_defaults(self):
        q = Quest(id="test", giver_role="староста", giver_node="start", title="Test", status="active", type="help")
        assert q.id == "test"
        assert q.progress == 0
        assert q.required == 0
        assert q.deliver_items is None
        assert q.deadline_day is None
        assert q.chain is None
        assert q.chain_step is None

    def test_quest_with_deliver_items(self):
        items = [{"name": "кинжал", "count": 5}]
        q = Quest(id="q1", giver_role="A", giver_node="n1", title="T", status="active", type="deliver", deliver_items=items)
        assert q.deliver_items == items

    def test_quest_with_deadline(self):
        q = Quest(id="q1", giver_role="A", giver_node="n1", title="T", status="active", type="help", required=3, deadline_day=10)
        assert q.deadline_day == 10

    def test_quest_chain_fields(self):
        q = Quest(id="pala_1", giver_role="A", giver_node="n1", title="T", status="active", type="chain", chain="pala", chain_step=1)
        assert q.chain == "pala"
        assert q.chain_step == 1


class TestCanGive:
    def test_can_give_no_active(self):
        st = make_state()
        assert quest_can_give("староста", st) is True

    def test_cannot_give_active_quest(self):
        st = make_state()
        st["hidden"]["quests_raw"].append({"id": "pala_1", "giver_role": "староста", "status": "active"})
        assert quest_can_give("староста", st) is False

    def test_cannot_give_blocked(self):
        st = make_state()
        st["hidden"]["role_quest_block"]["староста"] = 99
        assert quest_can_give("староста", st) is False

    def test_cannot_give_limit_3(self):
        st = make_state()
        st["hidden"]["quests_issued_today"]["start"] = 3
        assert quest_can_give("староста", st) is False

    def test_can_give_after_block_expires(self):
        st = make_state(day=100)
        st["hidden"]["role_quest_block"]["староста"] = 50
        assert quest_can_give("староста", st) is True

    def test_can_give_different_role(self):
        st = make_state()
        st["hidden"]["quests_raw"].append({"id": "pala_1", "giver_role": "староста", "status": "active"})
        assert quest_can_give("торговец", st) is True


class TestGive:
    def test_give_from_template(self):
        st = make_state()
        ok, msg = quest_give("pala_1", "староста", st)
        assert ok is True
        assert len(st["hidden"]["quests_raw"]) == 1
        q = st["hidden"]["quests_raw"][0]
        assert q["status"] == "active"
        assert q["type"] == "deliver"

    def test_give_unknown_returns_false(self):
        st = make_state()
        ok, msg = quest_give("nonexistent", "староста", st)
        assert ok is False

    def test_give_increments_issued_today(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        assert st["hidden"]["quests_issued_today"]["start"] == 1

    def test_give_sets_deadline(self):
        st = make_state()
        quest_give("pala_2", "староста", st)
        q = st["hidden"]["quests_raw"][0]
        assert q["deadline_day"] == 31  # day 1 + 30

    def test_give_sets_giver_node(self):
        st = make_state(node_id="forest_1")
        quest_give("pala_1", "староста", st)
        q = st["hidden"]["quests_raw"][0]
        assert q["giver_node"] == "forest_1"


class TestProgress:
    def test_help_progress(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        ok, msg = quest_progress("heretic_2", 1, st)
        assert ok is True
        q = quest_get_active("heretic_2", st)
        assert q.progress == 1

    def test_deliver_progress_error(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        ok, msg = quest_progress("pala_1", 1, st)
        assert ok is False

    def test_deceive_progress_error(self):
        st = make_state()
        quest_give("heretic_1", "староста", st)
        ok, msg = quest_progress("heretic_1", 1, st)
        assert ok is False

    def test_progress_no_active_quest(self):
        st = make_state()
        ok, msg = quest_progress("pala_1", 1, st)
        assert ok is False

    def test_progress_updates_dict(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        quest_progress("heretic_2", 2, st)
        d = st["hidden"]["quests_raw"][0]
        assert d["progress"] == 2


class TestDeceive:
    def test_deceive_success_roll(self):
        st = make_state()
        quest_give("heretic_1", "староста", st)
        # Mock dice.roll_d6 to return 6
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 6
        ok, msg = try_deceive("староста", "start", st)
        qmod.dice.roll_d6 = orig
        assert ok is True

    def test_deceive_fail_roll_rep_penalty(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 1
        ok, msg = try_deceive("староста", "start", st)
        qmod.dice.roll_d6 = orig
        assert ok is False
        rep = st["hidden"]["reputation"].get("староста", 0)
        assert rep == -1

    def test_deceive_cooldown_prevents_second_penalty(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 1
        try_deceive("староста", "start", st)
        rep_before = st["hidden"]["reputation"].get("староста", 0)
        try_deceive("староста", "start", st)
        rep_after = st["hidden"]["reputation"].get("староста", 0)
        assert rep_after == rep_before  # no second penalty

"""Tests for burt/quests.py -- section 18, 33, 36 spec."""
import pytest

from burt.quests import (
    Quest,
    quest_can_give,
    quest_give,
    quest_progress,
    try_deceive,
    quest_complete,
    quest_fail,
    expire_blockades,
    expire_deceit_penalties,
    quest_get_active,
)


def make_state(day=1, node_id="start", mode="exploring"):
    return {
        "visible": {
            "hp": 10, "hp_max": 10, "mp": 3, "mp_max": 3,
            "eat": True, "sleep_counter": 5, "date": f"{day} day",
            "effects": [],
            "location": {"name": "Crossroads", "exits": ["north"]},
            "inventory": [{"name": "кинжал гоблина", "count": 20},
                          {"name": "посох гоблина", "count": 2}],
            "wallet": {"gold": 0, "silver": 5, "copper": 0},
            "skills_visible": [],
            "quests_issued_today": {},
        },
        "hidden": {
            "current_mode": mode, "current_node_id": node_id,
            "day": day, "step": 0,
            "quests_raw": [],
            "role_quest_block": {},
            "quest_deceive_attempts": {},
            "deceit_penalty_until": {},
            "quests_issued_today": {},
            "killed_quest_givers": [],
            "reputation": {},
        },
    }


class TestQuestCreation:
    def test_quest_defaults(self):
        q = Quest(id="test", giver_role="староста", giver_node="start", title="Test", status="active", type="help")
        assert q.id == "test"
        assert q.progress == 0
        assert q.required == 0
        assert q.deliver_items is None
        assert q.deadline_day is None
        assert q.chain is None
        assert q.chain_step is None

    def test_quest_with_deliver_items(self):
        items = [{"name": "кинжал", "count": 5}]
        q = Quest(id="q1", giver_role="A", giver_node="n1", title="T", status="active", type="deliver", deliver_items=items)
        assert q.deliver_items == items

    def test_quest_with_deadline(self):
        q = Quest(id="q1", giver_role="A", giver_node="n1", title="T", status="active", type="help", required=3, deadline_day=10)
        assert q.deadline_day == 10

    def test_quest_chain_fields(self):
        q = Quest(id="pala_1", giver_role="A", giver_node="n1", title="T", status="active", type="chain", chain="pala", chain_step=1)
        assert q.chain == "pala"
        assert q.chain_step == 1


class TestCanGive:
    def test_can_give_no_active(self):
        st = make_state()
        assert quest_can_give("староста", st) is True

    def test_cannot_give_active_quest(self):
        st = make_state()
        st["hidden"]["quests_raw"].append({"id": "pala_1", "giver_role": "староста", "status": "active"})
        assert quest_can_give("староста", st) is False

    def test_cannot_give_blocked(self):
        st = make_state()
        st["hidden"]["role_quest_block"]["староста"] = 99
        assert quest_can_give("староста", st) is False

    def test_cannot_give_limit_3(self):
        st = make_state()
        st["hidden"]["quests_issued_today"]["start"] = 3
        assert quest_can_give("староста", st) is False

    def test_can_give_after_block_expires(self):
        st = make_state(day=100)
        st["hidden"]["role_quest_block"]["староста"] = 50
        assert quest_can_give("староста", st) is True

    def test_can_give_different_role(self):
        st = make_state()
        st["hidden"]["quests_raw"].append({"id": "pala_1", "giver_role": "староста", "status": "active"})
        assert quest_can_give("торговец", st) is True


class TestGive:
    def test_give_from_template(self):
        st = make_state()
        ok, msg = quest_give("pala_1", "староста", st)
        assert ok is True
        assert len(st["hidden"]["quests_raw"]) == 1
        q = st["hidden"]["quests_raw"][0]
        assert q["status"] == "active"
        assert q["type"] == "deliver"

    def test_give_unknown_returns_false(self):
        st = make_state()
        ok, msg = quest_give("nonexistent", "староста", st)
        assert ok is False

    def test_give_increments_issued_today(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        assert st["hidden"]["quests_issued_today"]["start"] == 1

    def test_give_sets_deadline(self):
        st = make_state()
        quest_give("pala_2", "староста", st)
        q = st["hidden"]["quests_raw"][0]
        assert q["deadline_day"] == 31  # day 1 + 30

    def test_give_sets_giver_node(self):
        st = make_state(node_id="forest_1")
        quest_give("pala_1", "староста", st)
        q = st["hidden"]["quests_raw"][0]
        assert q["giver_node"] == "forest_1"


class TestProgress:
    def test_help_progress(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        ok, msg = quest_progress("heretic_2", 1, st)
        assert ok is True
        q = quest_get_active("heretic_2", st)
        assert q.progress == 1

    def test_deliver_progress_error(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        ok, msg = quest_progress("pala_1", 1, st)
        assert ok is False

    def test_deceive_progress_error(self):
        st = make_state()
        quest_give("heretic_1", "староста", st)
        ok, msg = quest_progress("heretic_1", 1, st)
        assert ok is False

    def test_progress_no_active_quest(self):
        st = make_state()
        ok, msg = quest_progress("pala_1", 1, st)
        assert ok is False

    def test_progress_updates_dict(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        quest_progress("heretic_2", 2, st)
        d = st["hidden"]["quests_raw"][0]
        assert d["progress"] == 2


class TestDeceive:
    def test_deceive_success_roll(self):
        st = make_state()
        quest_give("heretic_1", "староста", st)
        # Mock dice.roll_d6 to return 6
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 6
        ok, msg = try_deceive("староста", "start", st)
        qmod.dice.roll_d6 = orig
        assert ok is True

    def test_deceive_fail_roll_rep_penalty(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 1
        ok, msg = try_deceive("староста", "start", st)
        qmod.dice.roll_d6 = orig
        assert ok is False
        rep = st["hidden"]["reputation"].get("староста", 0)
        assert rep == -1

    def test_deceive_cooldown_prevents_second_penalty(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 1
        try_deceive("староста", "start", st)
        rep_before = st["hidden"]["reputation"].get("староста", 0)
        try_deceive("староста", "start", st)
        rep_after = st["hidden"]["reputation"].get("староста", 0)
        assert rep_after == rep_before  # no second penalty

    def test_deceive_already_tried(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 6
        try_deceive("староста", "start", st)
        ok, msg = try_deceive("староста", "start", st)
        assert ok is False
    def test_deceive_attempts_key_format(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 6
        try_deceive("староста", "start", st)
        key = "start::староста"
        assert key in st["hidden"]["quest_deceive_attempts"]

    def test_deceive_increment_progress_on_success(self):
        st = make_state()
        quest_give("heretic_1", "староста", st)
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 6
        try_deceive("староста", "start", st)
        q = quest_get_active("heretic_1", st)
        assert q.progress == 1

    def test_deceive_different_node_different_attempt(self):
        st = make_state(node_id="forest_1")
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 6
        try_deceive("староста", "start", st)
        ok, msg = try_deceive("староста", "forest_1", st)
        assert ok is True

    def test_deceive_penalty_ttl_set(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 1
        try_deceive("староста", "start", st)
        ttl = st["hidden"]["deceit_penalty_until"].get("староста")
        assert ttl == 11  # day 1 + 10

    def test_deceive_success_no_penalty(self):
        st = make_state()
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 6
        try_deceive("староста", "start", st)
        assert "староста" not in st["hidden"]["deceit_penalty_until"]


class TestComplete:
    def test_complete_deliver_full(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        ok, msg = quest_complete("pala_1", st)
        assert ok is True
        q = quest_get_active("pala_1", st)
        assert q is None  # completed, not active

    def test_complete_deliver_partial_roll_1(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        st["visible"]["inventory"] = []
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 1
        ok, msg = quest_complete("pala_1", st)
        qmod.dice.roll_d6 = orig
        assert ok is False
        st = make_state()
        quest_give("pala_1", "староста", st)
        # Remove items so partial
        st["visible"]["inventory"] = []
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod.dice.roll_d6 = lambda: 1
        ok, msg = quest_complete("pala_1", st)
        qmod.dice.roll_d6 = orig
        assert ok is False

    def test_complete_help_full(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        quest_progress("heretic_2", 5, st)
        ok, msg = quest_complete("heretic_2", st)
        assert ok is True

    def test_complete_help_partial_roll_5(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        quest_progress("heretic_2", 2, st)
        import burt.quests as qmod
        qmod._templates_cache = None
        orig = qmod.dice.roll_d6
        qmod.dice.roll_d6 = lambda: 5
        ok, msg = quest_complete("heretic_2", st)
        qmod.dice.roll_d6 = orig
        assert ok is True

    def test_complete_no_active(self):
        st = make_state()
        ok, msg = quest_complete("pala_1", st)
        assert ok is False

    def test_complete_removes_items(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        inv_names = [i["name"] for i in st["visible"]["inventory"]]
        assert "кинжал гоблина" not in inv_names
        assert "посох гоблина" not in inv_names


class TestFail:
    def test_fail_sets_status(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        ok, msg = quest_fail("pala_1", st)
        assert ok is True
        q = quest_get_active("pala_1", st)
        assert q is None

    def test_fail_sets_block_day_plus_10(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_fail("pala_1", st)
        block = st["hidden"]["role_quest_block"].get("староста")
        assert block == 11

    def test_fail_killed_sets_negative_one(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        st["hidden"]["killed_quest_givers"].append("староста")
        quest_fail("pala_1", st)
        block = st["hidden"]["role_quest_block"].get("староста")
        assert block == -1

    def test_fail_no_active(self):
        st = make_state()
        ok, msg = quest_fail("pala_1", st)
        assert ok is False

    def test_fail_updates_dict(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_fail("pala_1", st)
        d = st["hidden"]["quests_raw"][0]
        assert d["status"] == "failed"


class TestExpireBlockades:
    def test_expire_ttl_blockade(self):
        st = make_state(day=100)
        st["hidden"]["role_quest_block"]["староста"] = 50
        expire_blockades(st)
        assert "староста" not in st["hidden"]["role_quest_block"]

    def test_permanent_blockade_stays(self):
        st = make_state(day=100)
        st["hidden"]["role_quest_block"]["староста"] = -1
        expire_blockades(st)
        assert "староста" in st["hidden"]["role_quest_block"]

    def test_future_blockade_not_expired(self):
        st = make_state(day=5)
        st["hidden"]["role_quest_block"]["староста"] = 50
        expire_blockades(st)
        assert "староста" in st["hidden"]["role_quest_block"]

    def test_empty_blocks_noop(self):
        st = make_state()
        expire_blockades(st)  # should not raise


class TestExpireDeceitPenalties:
    def test_expire_penalty(self):
        st = make_state(day=100)
        st["hidden"]["deceit_penalty_until"]["староста"] = 50
        expire_deceit_penalties(st)
        assert "староста" not in st["hidden"]["deceit_penalty_until"]

    def test_future_penalty_not_expired(self):
        st = make_state(day=5)
        st["hidden"]["deceit_penalty_until"]["староста"] = 50
        expire_deceit_penalties(st)
        assert "староста" in st["hidden"]["deceit_penalty_until"]

    def test_no_reputation_change(self):
        st = make_state(day=100)
        st["hidden"]["deceit_penalty_until"]["староста"] = 50
        st["hidden"]["reputation"]["староста"] = -1
        expire_deceit_penalties(st)
        assert st["hidden"]["reputation"]["староста"] == -1


class TestChain:
    def test_chain_next_step_created(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        # pala_2 should be created
        active_ids = [d["id"] for d in st["hidden"]["quests_raw"] if d["status"] == "active"]
        assert "pala_2" in active_ids

    def test_chain_string_id_reference(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        q2 = quest_get_active("pala_2", st)
        assert q2 is not None
        assert q2.chain == "pala"
        assert q2.chain_step == 2

    def test_chain_stub_final(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        quest_complete("pala_2", st)
        quest_complete("pala_3", st)
        # No more quests after pala_3 (stub final)
        active_count = sum(1 for d in st["hidden"]["quests_raw"] if d["status"] == "active")
        assert active_count == 0

    def test_chain_does_not_increment_issued(self):
        st = make_state()
        issued_before = st["hidden"]["quests_issued_today"].get("start", 0)
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        issued_after = st["hidden"]["quests_issued_today"].get("start", 0)
        assert issued_after == issued_before + 1  # only initial give increments


class TestEdgeCases:
    def test_double_give_same_role(self):
        import importlib
        import burt.quests as qmod
        importlib.reload(qmod)
        import burt.quests as qmod
        qmod._templates_cache = None
        qmod._templates_cache = None  # reset cache
        st = make_state()
        quest_give("pala_1", "староста", st)
        ok, msg = quest_give("pala_1", "староста", st)
        assert ok is False

    def test_missing_template(self):
        st = make_state()
        ok, msg = quest_give("nonexistent", "староста", st)
        assert ok is False

    def test_negative_progress(self):
        st = make_state()
        quest_give("heretic_2", "староста", st)
        ok, msg = quest_progress("heretic_2", -5, st)
        assert ok is True
        q = quest_get_active("heretic_2", st)
        assert q.progress == -5

    def test_get_active_returns_none_for_completed(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_complete("pala_1", st)
        assert quest_get_active("pala_1", st) is None

    def test_get_active_returns_none_for_failed(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        quest_fail("pala_1", st)
        assert quest_get_active("pala_1", st) is None

    def test_get_active_returns_quest(self):
        st = make_state()
        quest_give("pala_1", "староста", st)
        q = quest_get_active("pala_1", st)
        assert q is not None
        assert q.id == "pala_1"
