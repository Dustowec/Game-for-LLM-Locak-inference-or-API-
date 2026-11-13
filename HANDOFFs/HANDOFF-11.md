=====================================================================
BURT -- HANDOFF 11
Date: 13.11.2026
Project: BURT-AI (E:\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous: HANDOFF-10 (superseded by this)
Uncommitted at handoff write: YES (will be committed with this file)
=====================================================================

---------------------------------------------------------------------
LANGUAGE POLICY
---------------------------------------------------------------------

Game is FULLY ENGLISH (code, docstrings, UI, prompts, replicas,
quests, sensory report, combat messages, tests asserts).
Communication with user is RUSSIAN (chat, commits, docs for user).

If Cyrillic appears in source or UI — that is a BUG.

---------------------------------------------------------------------
SESSION SUMMARY (HANDOFF-11)
---------------------------------------------------------------------

1. Config & LLM Budget (P2):
   - config.MAX_TOKENS = 2048 (env override BURT_MAX_TOKENS).
   - config.LLM_TIMEOUT_SECONDS = 180.
   - llm_client logs usage (prompt, completion, finish) at INFO.
   - llm_client retries on empty content (finish_reason=length).
   - Removed truncations: full LLM answer logged, full error body in exceptions.

2. Loop & Parsing (P1):
   - parse_choice now uses rfind (last mention wins) + _ACTION_SYNONYMS.
   - Fixed movement failure bug: if HP drops to 0 from micro-event (e.g., lightning)
     on a normal 'fail', game_over is now correctly triggered.
   - osmotret punishment (3rd+ costs 1 HP) confirmed working and logged.

3. Main Orchestrator (P1):
   - Added _determine_death_cause (pure helper).
   - Added _log_death (WARNING with cause, step, day, hp, location).
   - Added _log_inject (INFO: mode, step, actions count, menu. DEBUG: full sensory+menu).
   - Added _log_result_events (all events at INFO, even [STATE]).
   - No LLM answer truncation (answer[:200] removed).

4. Prompts (P3):
   - Added STRICT RULES to BURT_SYSTEM_PROMPT:
     * Only choose actions present in MENU.
     * No phantom items (if not in [HANDS], it doesn't exist).
     * If [COMBAT] is present, choose ONLY attack, block, or flee.
     * Format: CHOICE: <number>.
   - Fixed copy-paste bug in tests/test_prompts.py (DIARY_SUMMARY checked MEMORY).

5. LLM Engine Compatibility (Gemma 3n):
   - Added fallback in call_llm: if engine rejects 'system' role with
     'roles must alternate' error, retry with role 'user' (copy of messages
     list, no mutation). Works around Gemma's Jinja template that strips
     system and fails alternation.

6. Hunger Inject Bug Fix:
   - OLD: should_inject_hunger returned True on steps 0 and 10 regardless
     of eat flag (boundary inject). This created a contradiction: [STATE]
     showed "Hunger: full" while inject said "You are hungry". Models got
     confused and ate bread while full.
   - NEW: inject strictly by eat flag: eat=True -> never; eat=False -> always.
   - HUNGER_HUNGRY_AT kept as legacy constant (not used in inject logic).
   - Hardcoded eat=True on start (state.py) unchanged; double-inject issue
     resolved at the inject layer.

7. Tests:
   - 1425 -> 1425+ passed.
   - Added TestBurtSystemPromptP3Rules, TestParseChoiceSynonyms,
     TestDetermineDeathCause, TestLogDeath, TestLogInject, TestLethalMovement,
     TestCallLlm::test_retry_with_user_when_system_fails,
     TestShouldInjectHunger (rewritten for eat-only contract).

---------------------------------------------------------------------
CURRENT STATE (13.11.2026)
---------------------------------------------------------------------

- 1425+ passed, 0 failed.
- `python main.py --new --max-steps 20 --log-level INFO` runs.
- Qwen 3.5 4B behaves well with new prompts (menu-only, no phantom items,
  combat mode respected).
- Gemma 3n-E4B works via 'system -> user' fallback (but plays robotically,
  only CHOICE: 0).
- Game survives to step 20 (forced sleep) — first time in history!
- Death logging works perfectly:
  "Burt died | cause=combat | step=19 day=1 hp=0 | location=Forest"
- Micro-events (tree, stone, lightning) are deadly as designed (hardcore).

---------------------------------------------------------------------
KNOWN ISSUES (next session)
---------------------------------------------------------------------

1. [MEDIUM] Loot after combat not collected.
   loop.py: _execute_combat outcome="burt_won" -> loot.collect_loot
   not called. Loot stays in enemy, not in inventory.

2. [MEDIUM] cast action in combat not implemented.
   combat.resolve_round has no action="cast".
   format_combat_report shows "cast" if spells_available.

3. [MEDIUM] diary / memory / epitaph not wired.
   DIARY_PROMPT, MEMORY_SUMMARY_PROMPT, SPIRIT_PROMPT unused in main.py.
   Need to wire them on sleep (day+1) and on death.

4. [LOW] Hardcoded eat=True on start (state.py).
   This is a temporary crutch from HANDOFF-10 to prevent early hunger
   death during testing. Needs real hunger mechanics once the game loop
   is stable. After fix: should_inject_hunger is already correct
   (eat-only), so removing the crutch is safe.

5. [LOW] LLM sometimes ignores micro-location context and tries to go
   "south" or "north" in menus that only have "go_back" and "go_forward".
   (Parsed correctly as go_back/go_forward by rfind, but text is funny).

6. [LOW] Gemma 3n-E4B via 'user' fallback loses system prompt authority
   and plays robotically (only CHOICE: 0 - osmotret spam). This is a
   model limitation, not a bug. Qwen is the recommended model.

---------------------------------------------------------------------
RECOMMENDED NEXT STEPS
---------------------------------------------------------------------

Priority 1 (1 hour): Loot + Cast
  - Implement loot.collect_loot in loop.py on "burt_won".
  - Implement action="cast" in combat.py (if spells_available).

Priority 2 (1-2 hours): Diary / Memory / Epitaph
  - Wire DIARY_PROMPT on sleep.
  - Wire MEMORY_SUMMARY_PROMPT on 10+ lives.
  - Wire SPIRIT_PROMPT on final death.

Priority 3 (30 min): Remove hardcoded eat=True
  - state.py: eat=False on start (real hunger from turn 1).
  - Verify hunger inject works correctly (it should, since
    should_inject_hunger is now eat-only).

---------------------------------------------------------------------
QUICK START COMMANDS
---------------------------------------------------------------------

  cd E:\Butr-Ai
  .\.venv\Scripts\pytest.exe tests/ -q          # 1425+ pass
  python main.py --new --max-steps 20 --log-level INFO

MODEL RECOMMENDATIONS (6 GB VRAM):
  - Qwen 3.5 4B (thinking on) + max_tokens=2048 — BEST
  - Gemma 3n-E4B (via system->user fallback) — WORKS, but robotic
  - Gemma 4 E2B (thinking on) — WORST (osmotret spammer)

MEMORY AID (all English):
  - loop.parse_choice(text, actions) -> Action
    * CHOICE: <number> (wins over text)
    * fallback: rfind of synonyms (_ACTION_SYNONYMS)
  - loop.execute_action(action, state, rng=None) -> ActionResult
    * micro-events (fail) CAN kill -> game_over=True
  - main._determine_death_cause(state, action) -> str
  - main._log_death, main._log_inject, main._log_result_events
  - config.MAX_TOKENS (env BURT_MAX_TOKENS), config.LLM_TIMEOUT_SECONDS
  - hunger.should_inject_hunger(step, eat) -> bool  # strictly eat-based
  - llm_client.call_llm: falls back system->user on 'roles must alternate'

TEST COUNTER: 1425+ passed.
  Last verified: 13.11.2026

=====================================================================
END OF HANDOFF 11.
=====================================================================