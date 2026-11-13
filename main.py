#!/usr/bin/env python3
"""main.py — BURT game entry point (async orchestrator).

One turn:
  1. Build sensory report from visible state.
  2. Inject hunger / sleep signals if needed.
  3. Build menu of available actions.
  4. Send report + menu to LLM.
  5. Parse the choice, execute the action.
  6. Post-turn: death check, forced sleep, day wrap, quest expiry.
  7. Save state.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import config
from burt import (
    dice,
    hunger,
    loop,
    llm_client,
    prompts,
    quests,
    sensory,
    sleep as sleep_mod,
    state as state_mod,
    state_io,
)


logger = logging.getLogger("burt.main")


# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

DEFAULT_STATE_PATH = Path("state.json")
DEFAULT_MAX_STEPS = 10_000
CONFIG_HASH = "v0.7.0"


# ---------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------

def _sync_meta_from_hidden(state: dict) -> None:
    hidden = state.setdefault("hidden", {})
    meta = state.setdefault("meta", {})
    if "step" in hidden:
        meta["step"] = hidden["step"]
    if "day" in hidden:
        meta["day"] = hidden["day"]
    visible = state.setdefault("visible", {})
    if "day" in hidden:
        visible["date"] = f"{hidden['day']} day"


def _sync_hidden_from_meta(state: dict) -> None:
    meta = state.setdefault("meta", {})
    hidden = state.setdefault("hidden", {})
    hidden.setdefault("step", meta.get("step", 0))
    hidden.setdefault("day", meta.get("day", 1))


def _ensure_runtime_fields(state: dict) -> None:
    hidden = state.setdefault("hidden", {})
    hidden.setdefault("resurrection_used_today", False)
    hidden.setdefault("micro_location", {"active": False})
    hidden.setdefault("combat", None)
    hidden.setdefault("current_mode", "exploring")
    hidden.setdefault("last_action", None)
    hidden.setdefault("same_action_count", 0)


# ---------------------------------------------------------------------
# New life
# ---------------------------------------------------------------------

def make_new_state(life: int = 1) -> dict:
    return state_mod.create_initial_state(
        life=life,
        session_uuid=str(uuid.uuid4()),
        config_hash=CONFIG_HASH,
        session_started=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------
# Logging helpers (П.2, П.3, П.4)
# ---------------------------------------------------------------------

def _determine_death_cause(state: dict, action: loop.Action) -> str:
    """П.2: pure helper to determine what killed Burt."""
    visible = state["visible"]
    hidden = state["hidden"]
    hp = visible.get("hp", 0)

    # 1. Combat action
    if action.key.startswith("attack_") or action.key in ("block", "flee"):
        return "combat"

    # 2. Micro event (god_wrath, stone, tree, etc.)
    micro = hidden.get("micro_location") or {}
    if micro.get("active") and micro.get("damage", 0) > 0:
        return micro.get("event_type", "micro_event")

    # 3. Osmotret penalty
    if action.key == "osmotret" and hidden.get("same_action_count", 0) >= 3:
        return "osmotret_penalty"

    # 4. Hunger (hp > 0 because hunger doesn't zero HP in state directly)
    if hp > 0 and not visible.get("eat", True) and hidden.get("step") in hunger.HUNGER_DEATH_AT:
        return "hunger"

    return "unknown"


def _log_death(state: dict, action: loop.Action) -> None:
    """П.2: log death with cause, step, day, hp, location."""
    visible = state["visible"]
    hidden = state["hidden"]
    cause = _determine_death_cause(state, action)
    
    logger.warning(
        "Burt died | cause=%s | step=%d day=%d hp=%d | location=%s",
        cause,
        hidden.get("step", 0),
        hidden.get("day", 1),
        visible.get("hp", 0),
        visible.get("location", {}).get("name", "Unknown")
    )


def _log_result_events(result: loop.ActionResult) -> None:
    """П.3: log all result events at INFO (noisy but explicit)."""
    for ev in result.events:
        logger.info("event: %s", ev)


def _log_inject(step: int, day: int, mode: str, menu: list[loop.Action], user_msg: str) -> None:
    """П.4: log LLM inject (header+menu INFO, full DEBUG)."""
    actions_str = ", ".join(f"{i}={a.key}" for i, a in enumerate(menu))
    logger.info(
        "inject | mode=%s | step=%d day=%d | actions=%d",
        mode, step, day, len(menu)
    )
    logger.info("inject menu: %s", actions_str)
    logger.debug("inject full:\n%s", user_msg)


# ---------------------------------------------------------------------
# Turn loop
# ---------------------------------------------------------------------

async def run_turn(state: dict, history: list[dict], rng, dry_run: bool) -> tuple[bool, list[dict]]:
    visible = state["visible"]
    hidden = state["hidden"]

    # ── 1. Sensory report ─────────────────────────────────────
    report = sensory.format_sensory_report(visible)

    # ── 2. Hunger / sleep injection ──────────────────────────
    step = hidden.get("step", 0)
    if hunger.should_inject_hunger(step, visible.get("eat", False)):
        report += "\n\nYou are hungry."
    if sleep_mod.should_inject_tired(step):
        report += "\n\nYou are tired." if step < 20 else "\n\nYou are very tired."

    # ── 3. Menu ───────────────────────────────────────────────
    menu = loop.build_menu(visible, state)

    # ── 4. Dry run: just print ────────────────────────────────
    if dry_run:
        print("=" * 60)
        print(f"[STEP {step}] day={hidden.get('day', 1)} mode={hidden.get('current_mode')}")
        print("-" * 60)
        print(report)
        print("-" * 60)
        print("Menu:")
        for i, a in enumerate(menu):
            print(f"  {i}. [{a.key}] {a.label}")
        print("=" * 60)
        return False, history

    # ── 5. LLM call ───────────────────────────────────────────
    menu_text = "\n".join(f"{i}. {a.label}" for i, a in enumerate(menu))
    user_msg = f"{report}\n\nMENU:\n{menu_text}\n\nCHOICE:"
    
    _log_inject(step, hidden.get("day", 1), hidden.get("current_mode", "exploring"), menu, user_msg)
    
    answer, history = await llm_client.call_llm(
        prompts.BURT_SYSTEM_PROMPT, user_msg, history,
    )
    
    # П.5: No truncation
    logger.info("LLM: %s", answer)

    # ── 6. Parse and execute ─────────────────────────────────
    action = loop.parse_choice(answer, menu)
    logger.info("Action: %s (%s)", action.key, action.label)
    result = loop.execute_action(action, state, rng=rng)

    _log_result_events(result)

    # ── 7. Save history (trim if too long) ───────────────────
    if len(history) > 40:
        history = history[-20:]

    # ── 8. Game over? ────────────────────────────────────────
    if result.game_over:
        _log_death(state, action)
        return True, history

    # ── 9. Post-turn: hunger death check ─────────────────────
    death_outcome = _check_hunger_death(state, rng)
    if death_outcome == "final_death":
        logger.warning(
            "Burt died | cause=hunger | step=%d day=%d hp=%d | location=%s",
            hidden.get("step", 0),
            hidden.get("day", 1),
            visible.get("hp", 0),
            visible.get("location", {}).get("name", "Unknown")
        )
        return True, history
    if death_outcome == "resurrected":
        visible["hp"] = 2
        hidden["hp_raw"] = 2
        hidden["resurrection_used_today"] = True
        logger.info("Resurrected by dice roll (2 HP)")

    # ── 10. Forced sleep on step 20 ──────────────────────────
    step_now = hidden.get("step", 0)
    chose_sleep = (action.key == "sleep")
    if sleep_mod.is_forced_sleep(step_now, chose_sleep):
        logger.info("Forced sleep (step 20)")
        _do_sleep(state)

    # ── 11. Daily expiry ─────────────────────────────────────
    quests.expire_blockades(state)
    quests.expire_deceit_penalties(state)

    # ── 12. Sync meta and save ───────────────────────────────
    _sync_meta_from_hidden(state)
    return False, history


def _check_hunger_death(state: dict, rng) -> str:
    visible = state["visible"]
    hidden = state["hidden"]
    step = hidden.get("step", 0)
    eat = visible.get("eat", False)
    used = hidden.get("resurrection_used_today", False)

    if step not in hunger.HUNGER_DEATH_AT:
        return "no_death"
    if eat:
        return "no_death"

    roll = rng() if not used else 0
    outcome = hunger.resolve_hunger(step, eat, used, roll)
    if outcome == hunger.HungerOutcome.RESURRECTED:
        return "resurrected"
    if outcome == hunger.HungerOutcome.FINAL_DEATH:
        return "final_death"
    return "no_death"


def _do_sleep(state: dict) -> None:
    visible = state["visible"]
    hidden = state["hidden"]
    hp_max = visible.get("hp_max", 10)
    mp_max = visible.get("mp_max", 3)
    new_hp, new_mp, new_effects = sleep_mod.apply_sleep(hp_max, mp_max)
    visible["hp"] = new_hp
    visible["mp"] = new_mp
    visible["effects"] = new_effects
    hidden["hp_raw"] = new_hp
    hidden["mp_raw"] = new_mp

    eat, res_used = hunger.reset_hunger_after_sleep()
    visible["eat"] = eat
    visible["sleep_counter"] = 0
    hidden["resurrection_used_today"] = res_used
    hidden["day"] = hidden.get("day", 1) + 1
    hidden["step"] = 0
    visible["date"] = f"{hidden['day']} day"
    logger.info("Slept. day=%d step=0", hidden["day"])


# ---------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------

async def game_loop(
    state: dict,
    history: list[dict],
    max_steps: int,
    dry_run: bool,
    state_path: Path,
) -> None:
    rng = dice.roll_d6
    step_count = 0

    while step_count < max_steps:
        try:
            game_over, history = await run_turn(state, history, rng, dry_run)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except Exception:
            logger.exception("Unhandled error in turn")
            raise

        step_count += 1

        if dry_run:
            break

        try:
            state_io.save_state(state_path, state)
        except Exception:
            logger.exception("Failed to save state")

        if game_over:
            logger.info("Game over. Rerun with --new to start a new life.")
            break

    logger.info("Loop finished after %d turns", step_count)


# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------

def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description="BURT game entry point")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH,
                        help=f"State file (default: {DEFAULT_STATE_PATH})")
    parser.add_argument("--new", action="store_true",
                        help="Start a new life (ignore existing state)")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                        help=f"Stop after N turns (default: {DEFAULT_MAX_STEPS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print report+menu, no LLM call")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    setup_logging(args.log_level)

    state_path = args.state
    if args.new:
        state = make_new_state(life=1)
        _sync_hidden_from_meta(state)
        _ensure_runtime_fields(state)
        logger.info("New state created (life=1)")
    elif state_io.state_exists(state_path):
        try:
            state = state_io.load_state(state_path)
            _sync_hidden_from_meta(state)
            _ensure_runtime_fields(state)
            logger.info("Loaded state from %s (life=%d, day=%d)",
                        state_path, state["meta"]["life"], state["meta"]["day"])
        except Exception:
            logger.exception("Failed to load state; starting new")
            state = make_new_state(life=1)
            _sync_hidden_from_meta(state)
            _ensure_runtime_fields(state)
    else:
        logger.info("No state at %s; starting new life", state_path)
        state = make_new_state(life=1)
        _sync_hidden_from_meta(state)
        _ensure_runtime_fields(state)

    if args.new or not state_io.state_exists(state_path):
        try:
            _sync_meta_from_hidden(state)
            state_io.save_state(state_path, state)
            logger.info("Initial state saved to %s", state_path)
        except Exception:
            logger.exception("Failed to save initial state")
            return 1

    history: list[dict] = []
    try:
        await game_loop(state, history, args.max_steps, args.dry_run, state_path)
    except KeyboardInterrupt:
        logger.info("Ctrl+C received; saving state")
    except Exception:
        logger.exception("Fatal error in game loop")
        return 1

    try:
        _sync_meta_from_hidden(state)
        state_io.save_state(state_path, state)
        logger.info("State saved to %s", state_path)
    except Exception:
        logger.exception("Failed final save")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))