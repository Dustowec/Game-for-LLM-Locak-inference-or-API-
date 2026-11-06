=====================================================================
BURT -- HANDOFF 6
Date: 15.10.2026
Project: BURT-AI (E:\\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous handoffs: HANDOFF-1.md through HANDOFF-5.md (all obsolete except HANDOFF-5.md)
=====================================================================

---------------------------------------------------------------------
IMPORTANT -- CHARACTER ENCODING RULE FOR FUTURE WORK
---------------------------------------------------------------------

CRITICAL LESSON FROM THIS SESSION:

PowerShell on Windows CORRUPTS Cyrillic UTF-8 characters when writing
files via heredocs, variable assignment ($script), and echo/appending.
First letter of Cyrillic words is dropped or replaced with garbage bytes.
Once corrupted, EVERY subsequent write makes it worse.

RULE FOR ALL FUTURE WORK:
ALL docstrings, comments, documentation strings in .py files MUST be in ENGLISH.
Test files (tests/*.py): English only for test names, assertions, docstrings.
Game modules (burt/*.py): English for all docstrings and comments.
Game text values (NPC dialogues, flavor text) may contain Cyrillic but should
preferably be stored in JSON/config files, not hardcoded in source code.

If you absolutely need Cyrillic in source code, construct via chr():
    RU = lambda *codes: "".join(chr(c) for c in codes)

DO NOT attempt to write Cyrillic literals into .py files through PowerShell.
This destroyed loop.py beyond recovery during this session.

=====================================================================

---------------------------------------------------------------------
SESSION SUMMARY (15.10.2026)
---------------------------------------------------------------------

What was created:
  - burt/llm_client.py   [CREATED] async LLM client (~90 lines, 28 tests)
  - burt/loop.py         [DELETED during session, FAILED TO RECOVER]

What was achieved:
  - llm_client.py passed 28 tests (call_llm with retry/fallback, create_chat_completion, backend switching)
  - loop.py was written once correctly but DELETED accidentally during encoding-fix attempts
  - Multiple recovery attempts failed due to PowerShell UTF-8 corruption
  - Final state: loop.py does NOT exist, must be recreated from scratch

Previous known good test count before loop deletion: ~1132
Current passing tests: 28 (only llm_client still exists)

=====================================================================

---------------------------------------------------------------------
FILE STATUS
---------------------------------------------------------------------

NEW FILES CREATED THIS SESSION:

1. burt/llm_client.py [ACTIVE, TESTED]
   - Async LLM HTTP client for LM Studio / OpenAI-compatible APIs
   - Functions: call_llm(), create_chat_completion(), extract_answer(), extract_finish_reason()
   - Retry logic: MAX_RETRIES=1 (tries twice total)
   - Fallback answer on double failure
   - Backend selection via config.BACKEND ('lm_studio' or 'openai')
   - Uses aiohttp for async HTTP calls
   - Tests: tests/test_llm_client.py (28 tests passing)
   - All docstrings in English (per new rule)

API surface:
     async def call_llm(system_msg, user_msg, messages_history=None) -> (str, list[dict])
     async def create_chat_completion(messages) -> dict
     def extract_answer(raw_response) -> str
     def extract_finish_reason(raw_response) -> Optional[str]

2. burt/loop.py [DELETED -- NEEDS RECREATION FROM SCRATCH]
   
   WAS PRESENT DURING SESSION (~430 lines) BUT IS NOW GONE.
   
   Before deletion it contained:
   - Action / ActionResult dataclasses
   - build_menu(visible, state) -> list[Action]
   - parse_choice(response, menu) -> Action
   - execute_action(action, state) -> ActionResult
   - do_go(), do_search(), do_sleep(), do_eat(), do_drink()
   - should_sleep(), on_death(), increment_step(), check_hunger_death()
   - error_result(), _resolve_location_name()
   - GameLoop class with load_or_create_state()

   BEFORE DELETION: 22/28 tests passed, 6 failing due to string encoding bugs.
   
   RECOVERY ATTEMPTS THAT FAILED:
   - Attempted fixes converted \\uXXXX to single backslash incorrectly
   - Each fix attempt further corrupted Cyrillic escape sequences
   - Deleted original thinking unrecoverable
   - Tried multiple regeneration scripts (mkloop, gen_loop, mkloop_final)
   - ALL generator scripts also corrupted by same encoding bug
   - No backup exists (git has no commit with loop.py yet)
   
   ACTION REQUIRED: WRITE loop.py COMPLETELY FROM SCRATCH.
   Specification provided in next section.

FILES UNCHANGED THIS SESSION:
   burt/state.py, state_io.py, dice.py, combat.py, bestiary.py,
   spawn.py, sensory.py, prompts.py, config.py, world.py, magic.py,
   hunger.py, sleep.py, trade.py, loot.py, replicas.py

=====================================================================

---------------------------------------------------------------------
SPECIFICATION: burt/loop.py (TO BE RECREATED)
---------------------------------------------------------------------

REQUIREMENTS:
  - All docstrings MUST be in English (per session encoding lesson)
  - Comments SHOULD be in English
  - Only game-visible TEXT values may contain Cyrillic

DATA STRUCTURES:

  @dataclass Action
    key: str           # unique identifier (go_north, sleep, eat_food...)
    label: str         # display text shown to player/LLM
    cost_free: bool    # if True, does not advance day counter
    target_id: str|None      # target enemy id for attacks
    item: str|None           # item name for trade/eat actions

  @dataclass ActionResult
    events: list[str]              # log events
    new_hp: int|None               # HP changes
    new_mp: int|None               # MP changes
    inventory_change: list[dict]   # added/removed items
    wallet_change: dict|None       # currency changes
    direction_moved: str|None      # move direction
    search_result: str|None        # search outcome
    combat_block: bool             # block chosen flag
    combat_attack_target: str|None # attack target
    combat_flee: bool              # flee action taken
    game_over: bool                # triggers new life
    death_roll: int|None           # d6 result on death

MODULE FUNCTIONS:

  build_menu(visible: dict, state: dict) -> list[Action]
    Context-dependent menu based on current_mode:
      'exploring' --> osmotret, go_N directions, search, sleep, eat, drink
      'combat'    --> attack_X, block, flee
      'dialog'    --> exit_dialog, future categories
  
  parse_choice(response: str, menu: list[Action]) -> Action
    Parses LLM response for ВЫБОР: marker (index number > prefix match > first item)
  
  execute_action(action: Action, state: dict) -> ActionResult
    Dispatches to handlers: go_N->do_go, search->do_search, etc.
  
  do_go(state, direction) -> ActionResult  # location movement
  do_search(state) -> ActionResult         # item search
  do_sleep(state) -> ActionResult          # rest/sleep cycle
  do_eat(state) -> ActionResult            # consume food
  do_drink(state) -> ActionResult          # consume water (TRAP per rules.txt)
  should_sleep(visible, state) -> bool     # check sleep conditions
  on_death(state, rng_func) -> ActionResult  # death/resurrection logic
  increment_step(state) -> None            # step+day counter
  check_hunger_death(state) -> None        # starvation check (steps 8,18)
  error_result(message) -> ActionResult    # error event
  _resolve_location_name(loc_type, node_id) -> str  # location naming

GAMELOOP CLASS:
  __init__(rng_func=None, llm_caller=None)
  load_or_create_state(path=None) -> dict
  _build_prompt(report, menu, visible) -> str
  _apply_result(result, state) -> None
  run_session(state_path) -> None  # full async game loop

INTEGRATION POINTS:
  - burt.state_io.load_state/save_state for persistence
  - burt.sensory.format_sensory_report for observation
  - burt.combat.resolve_round for battle resolution
  - burt.llm_client.call_llm for AI responses
  - config.DAY_STEPS, config.HUNGER_DEATH_AT thresholds

TEST REQUIREMENTS:
  - tests/test_loop.py must pass ALL tests (aim for 28+)
  - Mock external deps (state_io, sensory, combat, llm_client)
  - Deterministic dice rolls via injected rng_func

=====================================================================

---------------------------------------------------------------------
STILL OPEN ITEMS FROM HANDOFF-5.md
---------------------------------------------------------------------

COMPLETED THIS SESSION:
  [x] Кос. №1: dice.resolve_flee (confirmed OK, no changes)
  [x] Кос. №9: unified servant name служитель_церкви (6 files changed)
  [x] Кос. №2: refactored _enemy_spell (always roll attack)
  [x] Кос. №4: post-flee turn for enemies (cast/melee choice)
  [x] NEW: Created burt/llm_client.py with 28 passing tests

NEEDS NEXT SESSION:
  - [ ] Recreate burt/loop.py from scratch (see spec above)
  - [ ] Restore tests/test_loop.py (was 22/28 passing before loss)
  - [ ] Integration tests connecting llm_client + loop

PENDING FROM EARLIER HANDOFFS:
  - Кос. №3: counter to first enemy (confirmed OK, not a bug)
  - Кос. №5: ambush spawn confirmed by user
  - Кос. №7: combat report in sensory.py (waits for loop.py)
  - Кос. №10: old replica files (checked N/A)
  - Кос. №11: price update in spec v0.7.1 (manual update needed)

FUTURE PRIORITIES:
  1. Recreate loop.py (blocks everything else)
  2. Add integration tests
  3. npc.py (from HANDOFF-5 queue)
  4. quest system (quests.json/quests.py)
  5. Sensory combat report
  6. Update README.md (currently outdated at 632 tests)
  7. Finalize Правила.md

=====================================================================

---------------------------------------------------------------------
KNOWN BUGS AND EDGE CASES
---------------------------------------------------------------------

1. [NEW 15.10] PowerShell UTF-8 Corruption -- CRITICAL
   Files written/modified through PowerShell may have corrupted Cyrillic
   Workaround: Use Python direct writes; English-only content in heredocs
   
2. [FROM HANDOFF-5] combat._enemy_melee staff penalty behavior unclear
   Status: Deferred to combat refactoring phase

3. [FROM HANDOFF-5] sensory.py combat report not implemented
   Status: Blocks full loop functionality

=====================================================================

---------------------------------------------------------------------
NOTES FOR NEXT SESSION
---------------------------------------------------------------------

START HERE:
  1. DO NOT use PowerShell to write/modify any .py files
  2. Write loop.py entirely with English docstrings/comments
  3. After recreation, verify: pytest tests/test_loop.py -q (aim 28+ pass)
  4. Then: pytest -q (full suite, aim 1150+ tests)

QUICK START COMMANDS FOR NEXT SESSION:
  cd E:\\Butr-Ai
  .\\.venv\\Scripts\\pytest.exe tests/test_llm_client.py -q  # verify 28 pass
  # recreate loop.py following specification above
  .\\.venv\\Scripts\\pytest.exe tests/test_loop.py -q  # aim 28+ pass
  .\\.venv\\Scripts\\pytest.exe -q  # full suite

MEMORY AID:
  - llm_client.py works fine (28 tests, English docstrings)
  - loop.py needs recreation (spec in HANDOFF-6 section above)
  - Never trust PowerShell with Cyrillic in string operations
  - Git has NO commit with loop.py -- create one after successful recreation



====================================================================

---------------------------------------------------------------------
ARCHITECTURAL DECISIONS (confirmed 5.11.2026)
---------------------------------------------------------------------

build_menu(visible: dict) -> list[Action]
  - reads visible only, NO state access
  - context-free menu generation

execute_action(action: Action, state: dict) -> ActionResult
  - writes to state dict entirely
  - delegates to other modules (world.go, hunger.resolve, sleep.apply,
    combat.resolve_round, loot.collect_loot)

_resolve_location_name(loc_type: str, node_id: str) -> str
  - hardcoded mapping inside loop.py (~11 entries)
  - returns human-readable name for player
  - e.g. kustarnik + start_east -> Gusty thicket
  - will move to separate module if >50 types appear later

Rule: all docstrings/comments in English. No Cyrillic literals in .py.

====================================================================

====================================================================
END OF HANDOFF 6 (updated).
====================================================================