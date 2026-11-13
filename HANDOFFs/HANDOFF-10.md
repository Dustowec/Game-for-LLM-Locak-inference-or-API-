=====================================================================
BURT -- HANDOFF 10
Date: 13.11.2026
Project: BURT-AI (E:\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous: HANDOFF-1..9 (HANDOFF-9 obsolete, superseded by this)
Uncommitted at handoff write: NO
=====================================================================

---------------------------------------------------------------------
LANGUAGE POLICY
---------------------------------------------------------------------

Game is FULLY ENGLISH (code, docstrings, UI, prompts, replicas,
quests, sensory report, combat messages, tests asserts).
Communication with user is RUSSIAN (chat, commits, docs for user).

If Cyrillic appears in source or UI — that is a BUG.

---------------------------------------------------------------------
SESSION SUMMARY (HANDOFF-10)
---------------------------------------------------------------------

1. Game translated to English (was HANDOFF-9 task, completed).
   - burt/*.py: all literals English
   - prompts.py: 5 prompts English
   - replicas.json: 12 roles + 2 events English
   - quests_templates.json: titles + item names English
   - sensory.py: [STATE][LOCATION][HANDS][WALLET][SKILLS][COMBAT]
   - combat.py, loop.py: English messages
   - config.py: LOCATION_TYPES English
   - tests: 1354 passed after translation

2. main.py + burt/__main__.py — entry point created.
   - async game loop: sensory -> LLM -> parse -> execute -> save
   - CLI: --new, --state, --max-steps, --dry-run, --log-level
   - `python main.py` and `python -m burt` both work

3. Bug fixes after first launch:
   - llm_client.py: fixed double /v1/v1/chat/completions
     (base_url already had /v1, code added another)
   - loop.py: parse_choice now parses "CHOICE:" prefix
     (was looking for Cyrillic "Ы:")
   - loop.py: English strings for osmotret/sleep/error
     (were chr(0x43E)+... codes)
   - loop.py: eat_food / drink_water actions implemented
   - combat.py: hp clamped to max(0, hp) everywhere
     (was leaving hp=-4, broke validate_state)
   - state.py: eat=True (was False -> death on step 8)
   - state.py: inventory=[bread x2, water x1] (was empty)
   - state.py: last_action, same_action_count fields
   - main.py: _ensure_runtime_fields (resurrection_used_today,
     micro_location, last_action, same_action_count)
   - main.py: _sync_meta_from_hidden (meta.step/day <-> hidden)

4. Scared-behavior punishment (user idea, "evil master"):
   - 1st osmotret: normal
   - 2nd osmotret: warn "Nothing has changed. Satisfied?"
   - 3rd+ osmotret: -1 HP ("A branch whips your face")
   - Reset counter on any non-osmotret action
   - Only osmotret is punished (it's "safe/scared" action)
   - Verified working: HP 10 -> 4 after 8 osmotret

Tests: 1354 -> 1379 (+25: main.py tests, punishment tests,
       parse_choice synced).

---------------------------------------------------------------------
CURRENT STATE (13.11.2026)
---------------------------------------------------------------------

- 1379 passed, 0 failed
- `python main.py --new --max-steps 10 --log-level INFO` runs
- LLM responds (LM Studio on localhost:1234)
- Game loop works end-to-end
- Punishment works (verified via state.json: hp 10 -> 4)
- BUT: events not visible in INFO log (logger.debug)

---------------------------------------------------------------------
KNOWN ISSUES (next session)
---------------------------------------------------------------------

1. [HIGH] Events not logged at INFO level.
   main.py: `logger.debug("event: %s", ev)` — DEBUG only.
   At --log-level INFO, punishment messages invisible.
   FIX: change to logger.info() or logger.warning() for damage.

2. [HIGH] parse_choice picks FIRST mention, not LAST.
   Qwen: "I look around... I go north" -> picks osmotret
   (first in menu, mentioned first in text).
   FIX: use rfind() to find LAST mentioned action.
   Tests will need update (test_parse_choice).

3. [HIGH] max_tokens=512 may be too small for thinking models.
   Gemma 4 E2B with thinking: empty response on first turn
   (finish_reason=length).
   FIX: increase to 2048 (config.MAX_TOKENS), log finish_reason.

4. [MEDIUM] Model confuses modes.
   Qwen in combat: wrote "I walk north" + CHOICE: 1 (block).
   Sensory report has [COMBAT] but model ignores it.
   FIX: prompt — "If [COMBAT] in sensory, choose ONLY
   attack/block/flee".

5. [MEDIUM] eat_food / drink_water may not consume items.
   Not verified. Check state.json inventory after use.

6. [MEDIUM] Gemma 4 E2B with thinking is worse than Qwen 3.5 4B.
   Gemma: 8 osmotret in a row (HP dropped to 4, still looking).
   Qwen: moved, ate, attacked (mostly).
   RECOMMENDATION: Qwen 3.5 4B with thinking + max_tokens=2048.

7. [LOW] cast action in combat not implemented.
   combat.resolve_round has no action="cast".
   format_combat_report shows "cast" if spells_available.

8. [LOW] loot after combat not collected.
   _execute_combat outcome="burt_won" -> loot.collect_loot
   not called. Loot stays in enemy, not in inventory.

9. [LOW] diary / memory / epitaph not wired.
   DIARY_PROMPT, MEMORY_SUMMARY_PROMPT, SPIRIT_PROMPT unused.

---------------------------------------------------------------------
RECOMMENDED NEXT STEPS
---------------------------------------------------------------------

Priority 1 (30 min): fix logging + parse_choice rfind
  - main.py: logger.info for events
  - loop.py: parse_choice uses rfind (last mention wins)
  - tests: update test_parse_choice expectations
  - Result: visible punishment, model stops getting stuck

Priority 2 (15 min): max_tokens + finish_reason logging
  - config.MAX_TOKENS = 2048
  - llm_client.call_llm: log finish_reason if "length"
  - Result: no more empty responses from thinking models

Priority 3 (30 min): prompt improvements
  - BURT_SYSTEM_PROMPT: add "If [COMBAT], choose only
    attack/block/flee"
  - CHOICE: <number> instead of CHOICE: [item]
  - Result: model respects combat mode

Priority 4 (1-2 hours): cast, loot, diary, memory, epitaph
  - See known issues 7-9.

---------------------------------------------------------------------
QUICK START COMMANDS
---------------------------------------------------------------------

  cd E:\Butr-Ai
  .\.venv\Scripts\pytest.exe tests/ -q          # 1379 pass
  python main.py --new --max-steps 10 --log-level INFO
  python main.py --new --dry-run                # inspect state only
  python -m burt --new --max-steps 5            # via module

MODEL RECOMMENDATIONS (6 GB VRAM):
  - Qwen 3.5 4B (thinking on) + max_tokens=2048 — BEST
  - Gemma 4 E2B (thinking off) — fast, dumber
  - Gemma 4 E2B (thinking on) — WORST (8 osmotret)
  - Llama 3.1 8B Q4 — if fits, better quality
  - Phi-3.5-mini Q4 — if 7B doesn't fit

MEMORY AID (all English):
  - loop.execute_action(action, state, rng=None) -> ActionResult
    * osmotret: 3rd+ costs 1 HP, 2nd warns, 1st normal
    * counter reset on any non-osmotret action
    * go_*: movement roll (§10), on-entry encounter (§23)
    * go_back / go_forward: micro-location (§11)
    * search: forest table, rng() (deterministic)
    * sleep: HP/MP restore, day+1, step=0
    * eat_food: eat=True, +1 HP, remove bread from inventory
    * drink_water: remove water from inventory
    * combat actions: attack_X / block / flee
  - loop.parse_choice(text, actions) -> Action
    * CH OICE: <number> or <key> or <label> (case-insensitive)
    * fallback: first action (TODO: rfind for last mention)
  - state.py: eat=True, inventory=[bread x2, water x1]
  - hidden: last_action, same_action_count, resurrection_used_today,
    micro_location
  - main.py: _ensure_runtime_fields, _sync_meta_from_hidden
  - player name: Burt

TEST COUNTER: 1379 passed.
  Last verified: 13.11.2026

=====================================================================
END OF HANDOFF 10.
=====================================================================