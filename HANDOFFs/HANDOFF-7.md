=====================================================================
BURT -- HANDOFF 7
Date: 05.11.2026
Project: BURT-AI (E:\\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous handoffs: HANDOFF-1.md through HANDOFF-6.md (all obsolete except HANDOFF-5.md)
=====================================================================

---------------------------------------------------------------------
CHARACTER ENCODING RULE (from HANDOFF-6, still valid)
---------------------------------------------------------------------

PowerShell on Windows CORRUPTS Cyrillic UTF-8 characters.
Rule: ALL docstrings/comments in .py files MUST be in ENGLISH.
Cyrillic in source code via chr(): RU = lambda *codes: "".join(chr(c) for c in codes)
Game text values (NPC dialogues, flavor text) -> JSON/config files only.

NEW LESSON FROM HANDOFF-7:
- PowerShell $gen = @'...'@ DOES NOT preserve Unicode escapes correctly.
- Use Set-Content with -Encoding UTF8 for ASCII-only content.
- For files with Cyrillic, use Python scripts with chr() or base64.
- Always verify file encoding after creation.
  BOM = ef bb bf (remove it).

=====================================================================

---------------------------------------------------------------------
SESSION SUMMARY (05.11.2026)
---------------------------------------------------------------------

What was created:
  - burt/loop.py         [RECREATED] sync game-loop core (~250 lines, 28 tests)
  - burt/quests.py       [CREATED] quest system §18,33,36 (~420 lines, 57 tests)
  - quests_templates.json [CREATED] quest templates for pala/heretic chains
  - tests/test_integration.py [CREATED] integration tests (31 tests)

What was achieved:
  - loop.py: build_menu, parse_choice, execute_action, should_sleep, error_result
    - Events as list of short strings (not concatenated)
    - Attack key prefix matching (attack_wolf_1)
    - Location name mapping (11 types via chr())
  - quests.py: full quest lifecycle from templates
    - Give/progress/deceive/complete/fail
    - Chain progression (pala_1->pala_2->pala_3)
    - Deceive cooldown (rate limit: -1 rep per 10 days per NPC)
    - Partial completion via 1d6 (§18): 1-2 fail, 3-4 retry, 5-6 partial accept
    - Blockades: day+10 or permanent (-1 for killed quest giver)
  - Integration tests: full cycle sensory->LLM->parse->execute
  - All 1220 tests passing

Previous test count: 1132
Current passing tests: 1220 (+88)

=====================================================================

---------------------------------------------------------------------
FILE STATUS
---------------------------------------------------------------------

ACTIVE FILES CREATED/MODIFIED THIS SESSION:

1. burt/loop.py [ACTIVE, TESTED]
   - Sync game-loop core (~252 lines, 28 tests)
   - Action / ActionResult dataclasses
   - build_menu(visible, state) -> list[Action]
     - Modes: exploring, combat, dialog
     - Items: osmotret, directions, search, sleep, eat/drink, attack/block/flee
   - parse_choice(user_text, actions) -> Action
     - Priority: numbered choice "Ы: N", prefix match, fallback
   - execute_action(action, state) -> ActionResult
     - Events as list of short strings (NOT concatenated)
     - Attack key: startswith("attack_") not == "attack"
     - Sleep restores HP/MP to max, clears effects
     - Search uses dice.resolve_search()
   - should_sleep(visible, state) -> bool
     - Threshold: sleep_counter >= 20 OR hp < 25% max
   - error_result(msg) -> ActionResult
     - Events: ["ошибка: " + msg]
   - _resolve_location_name(loc_type, node_id) -> str
     - 11 location types mapped via chr() keys

2. burt/quests.py [ACTIVE, TESTED]
   - Quest system §18, 33, 36 (~423 lines, 57 tests)
   - Quest dataclass: id, giver_role, giver_node, title, status, type,
     progress, required, deliver_items, issued_day, deadline_day, chain, chain_step
   - Public API:
     quest_can_give(role, state) -> bool
     quest_give(quest_id, role, state) -> (ok, msg)
     quest_progress(quest_id, amount, state) -> (ok, msg)  # help only
     try_deceive(npc_role, node_id, state) -> (ok, msg)
     quest_complete(quest_id, state) -> (ok, msg)
     quest_fail(quest_id, state) -> (ok, msg)
     expire_blockades(state) -> None
     expire_deceit_penalties(state) -> None
     quest_get_active(quest_id, state) -> Quest | None
   - Templates loaded from quests_templates.json (cached)
   - State fields in hidden:
     quests_raw, role_quest_block, quest_deceive_attempts,
     deceit_penalty_until, quests_issued_today, killed_quest_givers

3. quests_templates.json [ACTIVE]
   - 6 quest templates: pala_1, pala_2, pala_3, heretic_1, heretic_2, heretic_3
   - Each template: chain, step, title, type, deliver_items/null, required/null,
     deadline_days/null, next_chain_step (string-id or null)

4. tests/test_integration.py [ACTIVE, TESTED]
   - Full cycle tests (31 tests)
   - Sensory report generation, system prompt construction
   - Exploration cycle: osmotret, go_north
   - Combat cycle: attack kill, block, flee
   - Parse choice edge cases
   - Should sleep integration
   - LLM client integration (extract_answer, extract_finish_reason)
   - State mutation consistency

5. tests/test_quests.py [ACTIVE, TESTED]
   - Quest system tests (57 tests)
   - TestQuestCreation, TestCanGive, TestGive, TestProgress
   - TestDeceive (roll >=3 success, <=2 fail, cooldown, attempt tracking)
   - TestComplete (deliver full/partial, help full/partial, 1d6 outcomes)
   - TestFail (block=day+10, killed=-1)
   - TestExpireBlockades, TestExpireDeceitPenalties
   - TestChain (next_chain_step, string-id, stub final)
   - TestEdgeCases (double give, missing template, negative progress)

TEMPLATE FILES:
  - presets/*.json (14 files) — NPC dialogue presets with quest_* sections
  - replicas.json — role/event replica pool

CLEANUP:
  - Removed temporary generator scripts (_gen_*.py, _fix*.py)
  - Removed loop_fixed.py (stale artifact)

=====================================================================

---------------------------------------------------------------------
KNOWN BUGS AND EDGE CASES
---------------------------------------------------------------------

1. [HANDOFF-6] PowerShell UTF-8 Corruption -- CRITICAL
   Files written/modified through PowerShell may have corrupted Cyrillic.
   Workaround: Use Python direct writes with chr(); English-only in heredocs.
   Status: Still active risk for any future file creation.

2. [HANDOFF-5] combat._enemy_spell block eats cast MP
   Status: Deferred (user said ignore).

3. [HANDOFF-5] combat._burt_flee counter at multiple enemies
   Status: Deferred (user said ignore).

4. [HANDOFF-5] spawn.spawn_ambush unconfirmed by spec
   Status: Deferred (user said ignore).

5. [NEW 05.11] quests.py _templates_cache stale between tests
   Fix: importlib.reload(qmod) or qmod._templates_cache = None in tests.
   Status: Fixed in test code, but note for future sessions.

=====================================================================

---------------------------------------------------------------------
PENDING FROM EARLIER HANDOFFS
---------------------------------------------------------------------

  - npc.py (from HANDOFF-5 queue) — ОТЛОЖЕН пользователем
  - Sensory combat report (§23) — формат [БОЙ] + противники + меню
  - Update README.md (currently outdated at 1220 tests)
  - Finalize Правила.md

=====================================================================

---------------------------------------------------------------------
FUTURE PRIORITIES
---------------------------------------------------------------------
  1. Sensory combat report (§23)
     - Add combat section to sensory.format_sensory_report()
     - Format: [БОЙ] + enemy names + combat menu hint
     - Depends on: combat.py (already done), sensory.py (already done)
     - Estimated: ~50 lines, ~15 tests

  2. Update README.md
     - Current: outdated at 632 tests
     - Target: 1220 tests, list all modules
     - Estimated: ~30 minutes

  3. npc.py
     - NPC dialogue system using replicas.json
     - Integrates with quests.py (quest give/check)
     - ОТЛОЖЕН пользователем ("в последнюю очередь")
     - Estimated: ~300 lines, ~40 tests

  4. quest_io.py (optional)
     - Read/write quests.json for persistence
     - Currently quests stored in state dict only
     - Estimated: ~100 lines, ~10 tests

=====================================================================

---------------------------------------------------------------------
QUICK START COMMANDS FOR NEXT SESSION
---------------------------------------------------------------------
  cd E:\\Butr-Ai
  .\\.venv\\Scripts\\pytest.exe tests/ -q          # verify 1220 pass
  .\\.venv\\Scripts\\pytest.exe tests/test_loop.py -q   # 28 pass
  .\\.venv\\Scripts\\pytest.exe tests/test_quests.py -q # 57 pass
  .\\.venv\\Scripts\\pytest.exe tests/test_integration.py -q # 31 pass

MEMORY AID:
  - loop.py: events = list of short strings, attack starts with "attack_"
  - quests.py: templates cached, reload between tests, cooldown = rate limit
  - Never trust PowerShell with Cyrillic in string operations
  - Git has NO commit with loop.py or quests.py yet

=====================================================================

END OF HANDOFF 7.
=====================================================================