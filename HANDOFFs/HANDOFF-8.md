=====================================================================
BURT -- HANDOFF 8
Date: 06.11.2026
Project: BURT-AI (E:\Butr-Ai)
Spec: v0.7.0
Status: IN DEVELOPMENT, TDD
Previous handoffs: HANDOFF-1 through HANDOFF-7 (all obsolete)
Git: commit e2444ab "Section 23 combat report + loop<->combat integration, 1286 tests"
=====================================================================

---------------------------------------------------------------------
CHARACTER ENCODING RULE (from HANDOFF-6/7, still valid)
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
SESSION SUMMARY (06.11.2026)
---------------------------------------------------------------------

Main task: close §23 combat sensory report + loop<->combat integration.

What was created:
  - burt/sensory.py         [MODIFIED] added format_combat_report
  - burt/loop.py            [REWRITTEN] combat delegates to combat.resolve_round
  - tests/test_sensory_combat.py [NEW] 31 tests
  - tests/test_loop_combat.py    [NEW] 30 tests
  - tests/test_loop.py           [RECREATED] 37 tests (was 28, lost, rewritten)
  - tests/test_integration.py    [MODIFIED] combat block rewritten
  - README.md                    [FULL REWRITE]
  - HANDOFFs/HANDOFF-8.md        [NEW] this file

What was achieved:
  - burt/sensory.format_combat_report(combat: CombatState, burt: BurtStats) -> str
    * [BOY] header + opponents + "Tvoy hod." + menu
    * Dead marked "(Myortv)"
    * HP/damage NOT shown, round/initiative NOT shown
    * Menu built from available actions:
        atakovat <target>  - per live enemy
        blokirovat         - if any alive
        bezhat             - if any alive AND no no_flee tag
        kastovat           - if burt.spells_available
  - loop.execute_action(action, state, rng=None)
    * rng defaults to dice.roll_d6
    * combat mode: reads hidden["combat"] (CombatState dict)
    * assembles BurtStats from visible + hidden["spells"]
    * calls combat.resolve_round
    * syncs hp/mp visible <-> hidden
    * writes back hidden["combat"] or clears on end
    * appends format_combat_report to events while ongoing
    * on burt_died: game_over=True, combat=None, mode=exploring
  - loop._build_combat_menu reads hidden["combat"] (not hidden["enemies"])
    * per live enemy: Action("attack_<id>")
    * block/flee if any alive
    * [] if combat is None
  - BurtStats assembly:
    * hp/hp_max/mp/mp_max from visible
    * spells_available = (spells.element is not None) or (spells.alignment is not None)
    * damage_min/max, master, modifier - DEFAULTS (weapon system not implemented)

Tests: 1220 -> 1286 (+66)
  - test_sensory_combat.py: 31
  - test_loop_combat.py: 30
  - test_loop.py: 37 (recreated from scratch, +9 vs original 28)
  - test_integration.py: rewritten combat block (count same or close)

Git:
  - Local commit e2444ab pushed to origin/main.
  - First commit since HANDOFF-5.
  - 27 files, +4428 -50.
  - HANDOFF-6 and HANDOFF-7 now tracked in git.

---------------------------------------------------------------------
INCIDENT LOG (important for process)
---------------------------------------------------------------------

1. tests/test_loop.py was DESTROYED during this session:
   - The patch intended for tests/test_integration.py (adding TestFullCycleCombat)
     was applied to tests/test_loop.py instead.
   - test_loop.py was overwritten with patch content, losing:
       imports, make_state helper, and ~28 original tests.
   - Not in git at the time -> unrecoverable from history.
   - VSCode Local History did not work for the user.
   - LESSON: ALWAYS commit working state to git before large patches.
   - test_loop.py was rewritten from scratch (37 tests).

2. vim / ^V incident:
   - User pressed Ctrl+V inside vim (verbatim insert) -> commit message = "^V".
   - Fixed via `git commit --amend -m "..."` and `git push --force-with-lease`.
   - LESSON: always use `git commit -m "..."` for short messages.
   - For long messages: `git config --global core.editor "notepad"`.

---------------------------------------------------------------------
FILE STATUS
---------------------------------------------------------------------

burt/sensory.py:
  - format_sensory_report(visible) - UNCHANGED (58 existing tests intact)
  - format_combat_report(combat, burt) - NEW (§23)
    * _combat_display_name: numbers only if type_count > 1
    * _is_no_flee: checks tags safely (handles None tags)
    * _build_combat_menu_lines: attack per alive, block, flee (if no no_flee), cast (if spells_available)

burt/loop.py:
  - Signature: execute_action(action, state, rng=None)
  - Combat branch: _execute_combat(action, state, rng)
  - BurtStats builder: _build_burt_stats(visible, hidden)
  - Combat menu: _build_combat_menu reads hidden["combat"]
  - Sleep now writes hp_raw/mp_raw to HIDDEN (was: visible - bug fixed)
  - go_ handles both graph shapes: {north: id} and {exits: {north: id}}
  - Imports: from burt import combat; from burt.combat import CombatState, BurtStats
    * Module-level combat import -> tests monkeypatch loop.combat
    * Class imports -> not mocked (data structures)

tests/test_loop.py (RECREATED, 37 tests):
  - make_state(mode="exploring") helper restored
  - TestBuildMenuExploring (10), TestBuildMenuDialog (1), TestBuildMenuCombat (4)
  - TestParseChoice (6), TestExecuteActionExploring (6)
  - TestShouldSleep (4), TestErrorResult (2), TestResolveLocationName (4)

tests/test_loop_combat.py (NEW, 30 tests):
  - TestBurtStatsAssembly (4) - via monkeypatch of loop.combat
  - TestAttack (5), TestBlock (2), TestFlee (3)
  - TestDeath (1), TestCombatReportInEvents (2)
  - TestStateSync (3), TestCombatMenu (2)
  - TestErrors (2), TestDefaultRng (1)
  - Helper _rng_from(values): stuck on last value (handles StopIteration)

tests/test_sensory_combat.py (NEW, 31 tests):
  - TestStructure (6), TestOpponents (6), TestHiddenInfo (6)
  - TestMenu (10), TestEdgeCases (3)

tests/test_integration.py (MODIFIED):
  - TestFullCycleCombat rewritten for hidden["combat"] model
  - Helpers: _fleeable_enemy_key, _put_combat
  - 5 tests: menu, attack_hp_drop, attack_kill, block, flee_success

README.md (FULL REWRITE):
  - 1286 tests (was 632)
  - Full module table (18 modules) with §TZ references
  - Full test file list (22 files)
  - Key mechanics section (dice, combat, quests, hunger/sleep)
  - Character encoding rules section
  - Updated "What's next" (6 items)

---------------------------------------------------------------------
KNOWN BUGS AND EDGE CASES
---------------------------------------------------------------------

1. [HANDOFF-6/7] PowerShell UTF-8 corruption -- CRITICAL
   Status: Still active risk. Follow encoding rules above.

2. [HANDOFF-5] combat._enemy_spell block eats cast MP
   Status: Deferred (user said ignore).

3. [HANDOFF-5] combat._burt_flee counter at multiple enemies
   Status: Deferred (user said ignore).

4. [HANDOFF-5] spawn.spawn_ambush unconfirmed by spec
   Status: Deferred (user said ignore).

5. [NEW 06.11] combat.resolve_round has no "cast" action
   Actor cannot cast spells in combat yet, even if spells_available.
   format_combat_report shows "kastovat" in menu, but
   loop._execute_combat has no branch for it.
   Status: Deferred (separate task).

6. [NEW 06.11] BurtStats is a stub
   damage_min=1, damage_max=2, master=0, modifier=0 - defaults.
   Weapon system and skill system not integrated.
   Status: Deferred (depends on weapon/skills system).

7. [NEW 06.11] No combat START in loop.py
   loop can continue combat (execute_action), but nothing sets
   hidden["combat"] = CombatState.to_dict() and current_mode="combat".
   Spawn/ambush/random encounter integration missing.
   Status: NEXT PRIORITY.

8. [NEW 06.11] [Tools] menu in combat absent
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
---------------------------------------------------------------------

1. Combat start (NEXT - blocks real gameplay)
   - Who sets hidden["combat"] and current_mode="combat"?
   - Sources:
       * spawn.spawn_ambush (already exists)
       * random encounter on move (dice on transition)
       * Burt attacks first (from explore mode)
   - CombatState construction: start_combat(enemy_keys, initiative)
   - Initiative: burt / enemy / random (§23)
   - Estimated: ~80 lines in loop.py, ~20 tests

2. npc.py - dialogue system
   - Uses replicas.json (already loaded via burt.replicas)
   - Integrates with quests.py (quest_give, quest_progress)
   - DEFERRED by user - do not start without approval
   - Estimated: ~300 lines, ~40 tests

3. I/O layer (memory, diary, quest_io, logging_async)
   - memory.py: §28, memory.json, summarization at 10+
   - diary.py: §29, diary.json, summarization every 5 days
   - quest_io.py: read/write quests.json (currently in state dict only)
   - logging_async.py: §38, §39
   - Estimated: memory ~120L/15T, diary ~120L/15T, quest_io ~100L/10T,
     logging ~100L/10T

4. Small combat debts (each small)
   - [Tools] in combat menu
   - Real BurtStats (weapon + skill integration)
   - cast action in combat

5. Finalize Pravila.md

---------------------------------------------------------------------
QUICK START COMMANDS FOR NEXT SESSION
---------------------------------------------------------------------

  cd E:\Butr-Ai
  .\.venv\Scripts\pytest.exe tests/ -q          # verify 1286 pass
  .\.venv\Scripts\pytest.exe tests/test_loop.py -v       # 37
  .\.venv\Scripts\pytest.exe tests/test_loop_combat.py -v # 30
  .\.venv\Scripts\pytest.exe tests/test_sensory_combat.py -v # 31
  .\.venv\Scripts\pytest.exe tests/test_sensory.py -v    # 58

MEMORY AID:
  - loop.execute_action(action, state, rng=None)
    * combat mode -> hidden["combat"] (dict) -> CombatState.from_dict
    * sync visible.hp <-> hidden.hp_raw after each round
    * events_llm + [BOY] report while ongoing
    * game_over=True on burt_died
  - sensory.format_combat_report(combat, burt) -> str
    * HP/damage NOT shown
    * dead marked (Myortv)
    * menu: atakovat/blokirovat/bezhat/kastovat
  - BurtStats has DEFAULTS for damage/master/modifier
  - hidden["enemies"] is DEAD - use hidden["combat"]
  - Git is CLEAN - commit before big changes, always.

TEST COUNTER: 1286 passed.
  Last verified: 06.11.2026

=====================================================================
END OF HANDOFF 8.
=====================================================================