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

Usage:
  python main.py                       # continue from state.json (or new)
  python main.py --state my.json       # custom state file
  python main.py --new                 # start a new life
  python main.py --max-steps 5         # stop after N steps (debug)
  python main.py --dry-run             # no LLM, print report+menu
  python main.py --log-level INFO      # logging verbosity
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
CONFIG_HASH = "v0.7.0"  # bump when config.py changes affect state


# ---------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------

def _sync_meta_from_hidden(state: dict) -> None:
    """Bring meta["step"] / meta["day"] in sync with hidden.

    loop.py writes hidden["step"] and hidden["day"];
    validate_state checks meta["step"] and meta["day"].
    Without this, save_state raises after the first turn.
    """
    hidden = state.setdefault("hidden", {})
    meta = state.setdefault("meta", {})
    if "step" in hidden:
        meta["step"] = hidden["step"]
    if "day" in hidden:
        meta["day"] = hidden["day"]
    # Also mirror date if loop wrote it
    visible = state.setdefault("visible", {})
    if "day" in hidden:
        visible["date"] = f"{hidden['day']} day"


def _sync_hidden_from_meta(state: dict) -> None:
    """Initial sync: hidden.step/day from meta (for fresh state)."""
    meta = state.setdefault("meta", {})
    hidden = state.setdefault("hidden", {})
    hidden.setdefault("step", meta.get("step", 0))
    hidden.setdefault("day", meta.get("day", 1))


def _ensure_runtime_fields(state: dict) -> None:
    """Add fields that main.py needs but state.py doesn't define yet."""
    hidden = state.setdefault("hidden", {})
    hidden.setdefault("resurrection_used_today", False)
    hidden.setdefault("micro_location", {"active": False})
    hidden.setdefault("combat", None)
    hidden.setdefault("current_mode", "exploring")


# ---------------------------------------------------------------------
# New life
# ---------------------------------------------------------------------

def make_new_state(life: int = 1) -> dict:
    """Create a fresh initial state."""
    return state_mod.create_initial_state(
        life=life,
        session_uuid=str(uuid.uuid4()),
        config_hash=CONFIG_HASH,
        session_started=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------
# Turn loop
# ---------------------------------------------------------------------

async def run_turn(state: dict, history: list[dict], rng, dry_run: bool) -> tuple[bool, list[dict]]:
    """Run one game turn. Return (game_over, history).

    game_over=True only on final death (§4). Resurrection and new life
    are handled by the caller.
    """
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
    answer, history = await llm_client.call_llm(
        prompts.BURT_SYSTEM_PROMPT, user_msg, history,
    )
    logger.info("LLM: %s", answer[:200])

    # ── 6. Parse and execute ─────────────────────────────────
    action = loop.parse_choice(answer, menu)
    logger.info("Action: %s (%s)", action.key, action.label)
    result = loop.execute_action(action, state, rng=rng)

    for ev in result.events:
        logger.debug("event: %s", ev)

    # ── 7. Save history (trim if too long) ───────────────────
    if len(history) > 40:
        # Keep last 20 messages (10 turns) + system is re-added each call
        history = history[-20:]

    # ── 8. Game over? ────────────────────────────────────────
    if result.game_over:
        logger.warning("Burt died (game_over)")
        return True, history

    # ── 9. Post-turn: hunger death check ─────────────────────
    death_outcome = _check_hunger_death(state, rng)
    if death_outcome == "final_death":
        logger.warning("Final death from hunger")
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

    # ── 11. Daily expiry (after sleep, if day changed) ───────
    # (cheap to call every turn, no-op if nothing expired)
    quests.expire_blockades(state)
    quests.expire_deceit_penalties(state)

    # ── 12. Sync meta and save ───────────────────────────────
    _sync_meta_from_hidden(state)
    return False, history


def _check_hunger_death(state: dict, rng) -> str:
    """Run hunger death check. Return 'no_death' | 'resurrected' | 'final_death'."""
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
    """Apply sleep effects and wrap the day."""
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
    """Run the game until death, max_steps, or Ctrl+C."""
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
            break  # one turn is enough for inspection

        # Save after each turn (atomic)
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

    # ── Load or create state ─────────────────────────────────
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

    # ── Save initial state (if new) ──────────────────────────
    if args.new or not state_io.state_exists(state_path):
        try:
            _sync_meta_from_hidden(state)
            state_io.save_state(state_path, state)
            logger.info("Initial state saved to %s", state_path)
        except Exception:
            logger.exception("Failed to save initial state")
            return 1

    # ── Run loop ─────────────────────────────────────────────
    history: list[dict] = []
    try:
        await game_loop(state, history, args.max_steps, args.dry_run, state_path)
    except KeyboardInterrupt:
        logger.info("Ctrl+C received; saving state")
    except Exception:
        logger.exception("Fatal error in game loop")
        return 1

    # ── Final save ───────────────────────────────────────────
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