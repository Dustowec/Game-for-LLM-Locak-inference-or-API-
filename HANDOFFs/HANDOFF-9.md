=====================================================================
BURT -- HANDOFF 10
Date: 12.11.2026
Project: BURT-AI (E:\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous handoffs: HANDOFF-1 through HANDOFF-9 (all obsolete)
Uncommitted at handoff write: NO (see commit message below)
=====================================================================

---------------------------------------------------------------------
LANGUAGE POLICY (NEW in HANDOFF-10)
---------------------------------------------------------------------

The game is FULLY ENGLISH:
  - All source code, docstrings, comments — ENGLISH.
  - All UI strings (sensory report, combat messages, prompts) — ENGLISH.
  - All NPC replicas (replicas.json) — ENGLISH.
  - All quest titles and item names — ENGLISH.
  - All prompts sent to the LLM — ENGLISH.
  - Tests assert against ENGLISH strings only.

Communication with the user is RUSSIAN:
  - Chat messages, explanations, commit messages for the team,
    documentation written for the user — RUSSIAN.
  - HANDOFFs may be written in English to avoid encoding issues,
    but user-facing docs — Russian.

Why: the game must not contain Cyrillic literals (model is small,
Latin script works better for it). The user, however, prefers
Russian for communication. Do not mix the two.

If you (the next agent) see Cyrillic in source code or UI strings —
that is a BUG, not a feature. See WHAT WAS DONE IN HANDOFF-10.

---------------------------------------------------------------------
SESSION SUMMARY (12.11.2026) -- HANDOFF-10
---------------------------------------------------------------------

Main task: translate the ENTIRE game to English.

What was done:
  1. Dictionary-based replacement of all Cyrillic literals in code.
     Tool: dict.json + translate_cyrillic.py (one-shot scripts,
     can be deleted after use; kept for reference).
     Files changed: burt/*.py (16 files), config.py,
     quests_templates.json, tests/*.py (24 files).
  2. prompts.py: all 5 system prompts translated to English
     (BURT_SYSTEM_PROMPT, SPIRIT_PROMPT, DIARY_PROMPT,
      DIARY_SUMMARY_PROMPT, MEMORY_SUMMARY_PROMPT).
  3. replicas.json: all 12 roles + 2 events fully translated.
     Keys are now English (elder, peasant, peasant_woman, blacksmith,
     merchant, guard, fisherman, child, veteran, cleric, necromancer,
     tavernkeeper; mage_event, preacher_event).
  4. quests_templates.json: titles and item names translated.
  5. sensory.py: UI section headers are now [STATE], [LOCATION],
     [HANDS], [WALLET], [SKILLS], [COMBAT]; directions north/east/
     south/west; effects blessed/cursed/full/hungry/tired/fresh/fine/
     okay/critical; currency gold/silver/copper; items "N pcs".
  6. combat.py: all combat messages in English ("You killed X.",
     "You hit X.", "You take a defensive stance.", "You fled.",
     "Failed to flee.", "Ambush!", enemy attack/spell/breath
     messages).
  7. loop.py: movement messages in English ("Failed to move X.
     Micro-event: Y. Took N damage.").
  8. config.py: LOCATION_TYPES and LOCATION_TYPE_ROLLS use English
     keys (crossroads, thicket, forest, field, steppe, swamp, river,
     road, village, temple, dungeon).
  9. Tests: all Russian asserts replaced with English ones.
     1354 passed, 0 failed.

What was NOT touched (intentionally):
  - presets/*.json (14 files) — real game data, restored from git
    after an accidental deletion. Do not delete again.
  - Comments and docstrings that are not game terms — left as-is;
    cosmetic translation is optional and does not affect the game.

Tools kept for reference (can be deleted):
  - dict.json             (80+ term pairs, RU -> EN)
  - translate_cyrillic.py (one-shot replacement script)
  - CyrDict.md            (original HANDOFF-10 dictionary)

Tests: 1345 -> 1354 (+9 net; +1 from prompts fix, +8 from sensory
       test sync; -0 because English asserts already matched new UI).

---------------------------------------------------------------------
CHARACTER NAME
---------------------------------------------------------------------

Player character name is BURT. In English code/UI — "Burt".
No Cyrillic variant should appear in source code anymore.

---------------------------------------------------------------------
KNOWN BUGS
---------------------------------------------------------------------

1. [HANDOFF-5] combat._enemy_spell block eats cast MP
   Status: Deferred (user said ignore).

2. [HANDOFF-5] combat._burt_flee counter at multiple enemies
   Status: Deferred (user said ignore).

3. [HANDOFF-8] combat.resolve_round has no "cast" action
   Actor cannot cast spells in combat yet, even if spells_available.
   format_combat_report shows "cast" in menu, but
   loop._execute_combat has no branch for it.
   Status: Deferred (separate task).

4. [HANDOFF-8] BurtStats is a stub
   damage_min=1, damage_max=2, master=0, modifier=0 - defaults.
   Weapon system and skill system not integrated.
   Status: Deferred (depends on weapon/skills system).

5. [HANDOFF-8] [Tools] menu in combat absent
   BurtStats has no fields for scrolls, potions, etc.
   format_combat_report does not output "[Tools]" line.
   Status: Deferred.

---------------------------------------------------------------------
PENDING FROM EARLIER HANDOFFS
---------------------------------------------------------------------

- npc.py (from HANDOFF-5 queue) - DEFERRED by user ("last priority")
- Finalize Pravila.md - drafts in rules/ already in git
- I/O layer: memory.py, diary.py, quests_io.py, logging_async.py

---------------------------------------------------------------------
FUTURE PRIORITIES

1. Random events on roll 5-6 (§10)
    - Movement "great": positive event (loot, blessing)  [DONE 9.3/9.4]
    - Movement "fail_bad": bad event (may trigger combat) [PARTIAL]

2. Combat debts (each small)
    - [Tools] in combat menu
    - Real BurtStats (weapon + skill integration)
    - cast action in combat

3. npc.py - dialogue system
    - Uses replicas.json (already loaded via burt.replicas)
    - Integrates with quests.py (quest_give, quest_progress)
    - DEFERRED by user - do not start without approval
    - Estimated: ~300 lines, ~40 tests

4. I/O layer (memory, diary, quest_io, logging_async)
     - memory.py: §28, memory.json, summarization at 10+
     - diary.py: §29, diary.json, summarization every 5 days
     - quest_io.py: read/write quests.json (currently in state dict only)
     - logging_async.py: §38, §39
     - Estimated: memory ~120L/15T, diary ~120L/15T, quest_io ~100L/10T,
       logging ~100L/10T

5. Finalize Pravila.md

---------------------------------------------------------------------
QUICK START COMMANDS FOR NEXT SESSION
---------------------------------------------------------------------

  cd E:\Butr-Ai
  .\.venv\Scripts\pytest.exe tests/ -q          # verify 1354 pass
  .\.venv\Scripts\pytest.exe tests/test_loop_combat_start.py -v
  .\.venv\Scripts\pytest.exe tests/test_loop.py -v
  .\.venv\Scripts\pytest.exe tests/test_state.py -v
  .\.venv\Scripts\pytest.exe tests/test_state_io.py -v
  .\.venv\Scripts\pytest.exe tests/test_loop_search_fix.py -v
  .\.venv\Scripts\pytest.exe tests/test_loop_movement_events.py -v
  .\.venv\Scripts\pytest.exe tests/test_prompts.py -v
  .\.venv\Scripts\pytest.exe tests/test_replicas.py -v
  .\.venv\Scripts\pytest.exe tests/test_sensory.py -v

MEMORY AID (all English now):
  - loop.execute_action(action, state, rng=None)
    * go_ : movement roll (§10) -> on-entry encounter (§23)
    * roll 1-2 on movement -> micro-location (§11) with 2 exits
    * go_back    -> returns to source node
    * go_forward -> moves to target node with on-entry encounter
    * on-entry into dangerous: 1-2 attack, 3-6 quiet
    * thicket -> always ambush, initiative="enemy"
    * combat mode -> hidden["combat"] (dict) -> CombatState.from_dict
    * sync visible.hp <-> hidden.hp_raw after each round
    * events_llm + [COMBAT] report while ongoing
    * game_over=True on burt_died
  - loop._start_combat(enemy_keys, initiative, hidden, visible) -> str
    * writes hidden["combat"], sets hidden["current_mode"]="combat"
    * returns format_combat_report(...)
  - loop._maybe_start_combat_on_enter(loc_type, hidden, visible, rng)
    * thicket -> ambush; dangerous -> 1-2 attack; safe -> None
  - sensory.format_combat_report(combat, burt) -> str
    * HP/damage NOT shown
    * dead marked (Dead)
    * menu: attack / block / flee / cast
  - dice.resolve_micro_event(roll, level) -> MicroEventResult
    * roll=1 -> stone (1d6), roll=2 -> tree (2d6)
    * roll=3 -> lightning (3d6), roll=4 -> god_wrath (1×lvl)
  - dice.calculate_micro_damage(micro_event, rng) -> int
  - dice.resolve_movement_event(roll, level, rng, hp_max, mp_max)
        -> MovementEventResult
    * roll 5 -> loot: gold=rng() (1..6)
    * roll 6 -> blessing: hp/mp restore capped
    * rolls 1-4 -> nothing; description = readable English text
    * called from loop.py go_ handler only when move_roll in (5,6)
      AND no combat
  - BurtStats has DEFAULTS for damage/master/modifier
  - hidden["enemies"] is DEAD - use hidden["combat"]
  - visible["state"] is DEAD - use hidden["current_mode"]
  - Location graph shape: {type, entered, exits: {north,south,east,west}}
  - STARTING_NODE_ID = "start"
  - STARTING_LOCATION_NAME = "Crossroads"
  - Player name: "Burt" (no Cyrillic variant anywhere)
  - Git is CLEAN - commit before big changes, always.

TEST COUNTER: 1354 passed.
  Last verified: 12.11.2026
  Added in HANDOFF-10: +9 net (prompts + sensory test sync)

FOUND LATER (verified):
  - The double `step += 1` in `search` is a genuine bug - fixed
    in HANDOFF-9.2, now exactly one increment per search call.
  - hidden["location_types"] no longer exists in the new state.py;
    searches are now always performed against the forest table.
  - "step at the start of combat" - incorrect, removed from todo.

=====================================================================
END OF HANDOFF 10.
=====================================================================