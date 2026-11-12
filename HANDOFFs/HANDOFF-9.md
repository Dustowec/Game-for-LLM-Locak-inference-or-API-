=====================================================================
BURT -- HANDOFF 9
Date: 07.11.2026
Project: BURT-AI (E:\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous handoffs: HANDOFF-1 through HANDOFF-8 (all obsolete)
Uncommitted at handoff write: NO (see commit message below)
=====================================================================

---------------------------------------------------------------------
CHARACTER ENCODING RULE (from HANDOFF-6/7/8, still valid)
---------------------------------------------------------------------

PowerShell on Windows CORRUPTS Cyrillic UTF-8 characters.

Rules (STRICT):
- ALL docstrings/comments in .py files MUST be in ENGLISH.
- Cyrillic in source code via chr():
    RU = lambda *codes: "".join(chr(c) for c in codes)
- Game text values (NPC dialogues, flavor text) -> JSON/config only.
- Do NOT use PowerShell $gen = @'...'@ for Unicode content.
- Use Set-Content -Encoding UTF8 for ASCII-only.
- For Cyrillic, use Python scripts with chr() or base64.
- ALWAYS verify file encoding after creation.
  BOM = ef bb bf (must be removed).
- HANDOFFs written in ENGLISH to avoid encoding issues on write.

---------------------------------------------------------------------
CHARACTER NAME
---------------------------------------------------------------------

Player character name is BURT (Бурт), NOT "Бёрт".
Latin "burt" in code is fine. In Russian docs/comments/HANDOFFs
use "Бурт" only. This was explicitly fixed by user in this session.

---------------------------------------------------------------------
SESSION SUMMARY (07.11.2026)
---------------------------------------------------------------------

Main task: implement combat START in loop.py (HANDOFF-8 item 7).
Also aligned state.py with world.py graph shape.

Decisions from user (this session):
  O1: combat starts via on-entry roll (roll when entering a location).
  O2: two rolls per transition per spec (movement + on-entry).
  O3: approved - won -> target location, fled -> back, died -> death.
  O4: Burt attacks first - NOT implemented, explicitly deferred
      until npc.py (TODO in code).

What was created:
  - burt/state.py               [MODIFIED] graph shape, current_mode
  - burt/loop.py                [MODIFIED] combat start + movement roll
  - tests/test_loop_combat_start.py [NEW] 28 tests
  - tests/test_state.py         [MODIFIED] 4 tests
  - tests/test_state_io.py      [MODIFIED] 1 test
  - tests/test_loop.py          [MODIFIED] make_state + 1 test
  - tests/test_integration.py   [MODIFIED] make_state + 1 test
  - HANDOFFs/HANDOFF-9.md       [NEW] this file

What was achieved:

  1. state.py aligned with world.py:
     - STARTING_NODE_ID = "start" (was "node_start")
     - location_graph built via world.create_start_graph()
       (shape: {type, entered, exits} instead of flat {north, south, ...})
     - visible["state"] REMOVED; hidden["current_mode"] is now
       the single source of mode (VALID_STATES still enforced)
     - validate_state updated for new graph shape and current_mode

   2. loop.py: combat start (O1/O2/O3):
      - _start_combat(enemy_keys, initiative, hidden, visible) -> str
        * combat.start_combat -> hidden["combat"]
        * hidden["current_mode"] = "combat"
        * returns sensory.format_combat_report(...)
      - _maybe_start_combat_on_enter(location_type, hidden, visible, rng)
        * кустарник -> spawn.spawn_ambush, initiative="enemy"
        * dangerous (лес/поле/степь/болото/подземелье):
            roll 1-2 -> spawn.spawn_random, initiative="enemy"
            roll 3-6 -> quiet (None)
        * safe (река/дорога/деревня/храм/старт) -> None
      - _enter_new_node(graph, node_id, rng)
        * calls world.enter_node with normalized rolls
        * normalizes roll_size for roll_type=5 (1..3)
      - _handle_movement_failure(direction, move_result, hidden, visible, rng)
        * §11: creates micro-location with source/target/direction
        * rolls micro-event (stone/tree/lightning/god_wrath)
        * applies damage: stone 1d6, tree 2d6, lightning 3d6, god_wrath 1×lvl
        * stores micro_location in hidden state
      - go_ handler in execute_action:
        * movement roll via dice.resolve_movement (§10)
        * roll 1-2 -> _handle_movement_failure (micro-location)
        * roll 3-6 -> move, generate new node, on-entry roll
        * on entry into combat -> returns [БОЙ] report in events
      - go_back handler (§11): returns to source node, clears micro_location
      - go_forward handler (§11): moves to target node, on-entry encounter

  3. Menu in exploring: TODO(O4) comment added.
     Burt does NOT have attack_* in exploring menu (deferred).

Tests: 1286 -> 1314 (+28)
  - test_loop_combat_start.py: 28 (new file)
    * TestStartCombat (6)
    * TestMovementRoll (6)
    * TestOnEntryEncounter (7)
    * TestNewNodeGeneration (4)
    * TestCombatReportInEvents (2)
    * TestTodos (3)
  - test_state.py: 4 tests rewritten
  - test_state_io.py: 1 test rewritten
  - test_loop.py: make_state rewritten + 1 test
  - test_integration.py: make_state rewritten + 1 test

What DOES NOT work yet (explicit TODOs in code):
  - §11: micro-location on movement failure -> COMPLETED (12.11.2026)
    * Micro-location created on movement failure with 2 exits (back/forward)
    * Damage applied: stone 1d6, tree 2d6, lightning 3d6, god's wrath 1×lvl
  - O4: Burt attacks first (initiate combat from exploring).
      Deferred until npc.py: no enemy sources in exploring yet.
  - §10: positive events on movement/entry roll 5-6.
    Not implemented (loot, blessing, etc.).
  - §10: bad event on movement fail roll 1.
    Deferred except combat case.

Known issues found during this session (TODO for later):
   1. STARTING_LOCATION_NAME = "Развилка" (state.py) vs
      _LOCATION_NAMES["старт"] = "Crossroads" (loop.py).
      On return to start, name flips to "Crossroads".
   2. test_validate_spells_both_light_and_dark_forbidden in
      test_state.py does not actually test anything
      (single alignment field). Leave as-is.

Fixed (HANDOFF-9.2, 12.11.2026):
   - double `step += 1` in `search` — removed, now exactly one increment
     per search call.
   - `search` referenced removed `hidden["location_types"]`; search now
     always uses the forest table.
   - Note: `hidden["location_types"]` no longer exists in `state.py`.

---------------------------------------------------------------------
KNOWN BUGS (from earlier handoffs, still active)
---------------------------------------------------------------------

1. [HANDOFF-6/7/8] PowerShell UTF-8 corruption -- CRITICAL
   Status: Still active risk. Follow encoding rules above.

2. [HANDOFF-5] combat._enemy_spell block eats cast MP
   Status: Deferred (user said ignore).

3. [HANDOFF-5] combat._burt_flee counter at multiple enemies
   Status: Deferred (user said ignore).

4. [HANDOFF-5] spawn.spawn_ambush unconfirmed by spec
   Status: RESOLVED in this session (user approved ambush on entry
   to кустарник, initiative="enemy").

5. [HANDOFF-8] combat.resolve_round has no "cast" action
   Actor cannot cast spells in combat yet, even if spells_available.
   format_combat_report shows "kastovat" in menu, but
   loop._execute_combat has no branch for it.
   Status: Deferred (separate task).

6. [HANDOFF-8] BurtStats is a stub
   damage_min=1, damage_max=2, master=0, modifier=0 - defaults.
   Weapon system and skill system not integrated.
   Status: Deferred (depends on weapon/skills system).

7. [HANDOFF-8] [Tools] menu in combat absent
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
    - Movement "great": positive event (loot, blessing)
    - Movement "fail_bad": bad event (may trigger combat)
    - Currently only combat branch implemented for fail_bad
    - Estimated: ~40 lines, ~12 tests

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

§11 micro-location: COMPLETED (12.11.2026)
     - _handle_movement_failure creates micro-location with source/target
     - go_back: returns to source node
     - go_forward: moves to target node with on-entry encounter
     - Damage events: stone 1d6, tree 2d6, lightning 3d6, god_wrath 1×lvl
     - 17 new tests added

Search fixes (HANDOFF-9.2, 12.11.2026): COMPLETED
      - double `step += 1` in `search` removed
      - `search` no longer references `hidden["location_types"]`
      - always uses forest table directly
      - search uses rng() instead of dice.roll_d6() (deterministic)
      - 4 new tests added

---------------------------------------------------------------------
QUICK START COMMANDS FOR NEXT SESSION
---------------------------------------------------------------------

  cd E:\Butr-Ai
   .\.venv\Scripts\pytest.exe tests/ -q          # verify 1335 pass
   .\.venv\Scripts\pytest.exe tests/test_loop_combat_start.py -v # 45
   .\.venv\Scripts\pytest.exe tests/test_loop.py -v             # 37
   .\.venv\Scripts\pytest.exe tests/test_state.py -v            # ~60
   .\.venv\Scripts\pytest.exe tests/test_state_io.py -v         # ~30
   .\.venv\Scripts\pytest.exe tests/test_loop_search_fix.py -v  # 4

MEMORY AID:
  - loop.execute_action(action, state, rng=None)
    * go_ now: movement roll (§10) -> on-entry encounter (§23)
    * roll 1-2 on movement -> micro-location (§11) with 2 exits
    * go_back -> returns to source node
    * go_forward -> moves to target node with on-entry encounter
    * on-entry into dangerous: 1-2 attack, 3-6 quiet
    * кустарник -> always ambush, initiative="enemy"
    * combat mode -> hidden["combat"] (dict) -> CombatState.from_dict
    * sync visible.hp <-> hidden.hp_raw after each round
    * events_llm + [БОЙ] report while ongoing
    * game_over=True on burt_died
  - loop._start_combat(enemy_keys, initiative, hidden, visible) -> str
    * writes hidden["combat"], sets hidden["current_mode"]="combat"
    * returns format_combat_report(...)
  - loop._maybe_start_combat_on_enter(loc_type, hidden, visible, rng)
    * кустарник -> ambush; dangerous -> 1-2 attack; safe -> None
  - sensory.format_combat_report(combat, burt) -> str
    * HP/damage NOT shown
    * dead marked (Myortv)
    * menu: atakovat/blokirovat/bezhat/kastovat
  - dice.resolve_micro_event(roll, level) -> MicroEventResult
    * roll=1 -> stone (1d6), roll=2 -> tree (2d6)
    * roll=3 -> lightning (3d6), roll=4 -> god_wrath (1×lvl)
  - dice.calculate_micro_damage(micro_event, rng) -> int
  - BurtStats has DEFAULTS for damage/master/modifier
  - hidden["enemies"] is DEAD - use hidden["combat"]
  - visible["state"] is DEAD - use hidden["current_mode"]
  - Location graph shape: {type, entered, exits: {north,south,east,west}}
  - STARTING_NODE_ID = "start"
  - Player name in Russian: "Бурт" (not "Бёрт")
  - Git is CLEAN - commit before big changes, always.

TEST COUNTER: 1335 passed.
  Last verified: 12.11.2026
  Added: 17 micro-location tests (HANDOFF-9.1) + 4 search fix tests (HANDOFF-9.2)

=====================================================================
END OF HANDOFF 9.
=====================================================================
found later:
The double `step += 1` in `search` is a genuine bug—it’s just one line of code.
hidden["location_types"]` no longer exists in the new `state.py`; searches are now always performed against the forest table.
Point 2 (“step at the start of combat”) is incorrect; remove it.