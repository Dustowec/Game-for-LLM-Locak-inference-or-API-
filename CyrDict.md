# CYRILLIC → ENGLISH DICTIONARY
# HANDOFF-10: Replace ALL Cyrillic literals with English
# Exception: HANDOFFs documentation files

## 1. LOCATION TYPES (world.py → loop.py → state.py)
| Cyrillic | English | Files |
|----------|---------|-------|
| старт | crossroads | world, loop._LOCATION_NAMES |
| кустарник | thicket | world, loop._ENCOUNTER_LOCATIONS, loop._AMBUSH_LOCATION |
| лес | forest | world, loop._ENCOUNTER_LOCATIONS |
| поле | field | world, loop._ENCOUNTER_LOCATIONS |
| степь | steppe | world, loop._ENCOUNTER_LOCATIONS |
| болото | swamp | world, loop._ENCOUNTER_LOCATIONS |
| река | river | world |
| дорога | road | world |
| деревня | village | world |
| храм | temple | world |
| подземелье | dungeon | world, loop._ENCOUNTER_LOCATIONS |

## 2. ROLE NAMES (state.py → trade.py → quests.py → presets/)
| Cyrillic | English | Files |
|----------|---------|-------|
| торговец | merchant | state, trade |
| стражник | guard | state |
| крестьянин | peasant | state |
| староста | elder | state, trade |
| трактирщик | tavernkeeper | state, trade |
| кузнец | blacksmith | state, trade |
| рыбак | fisherman | state, trade |
| ребёнок | child | state |
| ветеран | veteran | state |
| служитель_церкви | cleric | state, magic |
| чернокнижник | necromancer | state, magic, trade |
| маг | mage | state, magic, trade |

## 3. MAGIC ELEMENTS & ALIGNMENTS (magic.py → state.py)
| Cyrillic | English | Files |
|----------|---------|-------|
| огонь | fire | magic.ELEMENTS |
| вода | water | magic.ELEMENTS |
| земля | earth | magic.ELEMENTS |
| воздух | air | magic.ELEMENTS |
| свет | light | magic.ALIGNMENTS |
| тьма | dark | magic.ALIGNMENTS |

## 4. ENEMY NAMES & WEAPONS (bestiary.py)
| Cyrillic | English | Files |
|----------|---------|-------|
| гоблин | goblin | bestiary.name |
| гоблин-шаман | goblin_shaman | bestiary.name |
| волк | wolf | bestiary.name |
| кабан | boar | bestiary.name |
| бандит | bandit | bestiary.name |
| медведь | bear | bestiary.name |
| дракон | dragon | bestiary.name |
| кинжал гоблина | goblin_dagger | bestiary.weapon, loot, trade |
| колдовской посох гоблина | goblin_staff | bestiary.weapon, loot, trade |
| клыки | fangs | bestiary.weapon, loot, trade |
| когти и зубы | claws_and_teeth | bestiary.weapon |
| меч | sword | bestiary.weapon |
| меч низкого качества | low_quality_sword | trade, loot |
| меч обычный | ordinary_sword | trade |
| меч высокого качества | high_quality_sword | trade |
| чешуя дракона | dragon_scale | loot |
| драконьи клыки | dragon_fangs | loot |
| кость дракона | dragon_bone | loot |
| повязка | bandage | loot |

## 5. TRADE ITEMS (trade.py)
| Cyrillic | English | Files |
|----------|---------|-------|
| хлеб | bread | trade.BASE_PRICES |
| рыба | fish | trade.BASE_PRICES |
| вяленая рыба | dried_fish | trade.BASE_PRICES |
| фляга с водой | waterskin | trade.BASE_PRICES |
| фляга с водой большая | large_waterskin | trade.BASE_PRICES |
| спальный мешок | bedroll | trade.BASE_PRICES |
| комната в таверне | tavern_room | trade.BASE_PRICES |
| дубина | club | trade.BASE_PRICES |
| копьё | spear | trade.BASE_PRICES |

## 6. SENSORY REPORT HEADERS (sensory.py)
| Cyrillic | English |
|----------|---------|
| [СОСТОЯНИЕ] | [STATE] |
| [МЕСТО] | [LOCATION] |
| [РУКИ] | [HANDS] |
| [КОШЕЛЁК] | [WALLET] |
| [НАВЫКИ] | [SKILLS] |
| [БОЙ] | [COMBAT] |
| пусто | empty |
| дата | date |

## 7. DIRECTION TRANSLATIONS (sensory.py)
| Cyrillic | English |
|----------|---------|
| север | north |
| восток | east |
| юг | south |
| запад | west |

## 8. STATUS TEXTS (sensory.py)
| Cyrillic | English |
|----------|---------|
| благословлён | blessed |
| проклят | cursed |
| сыт | full |
| голоден | hungry |
| устал | tired |
| сильно устал | very tired |
| в порядке | fine |
| нормально | okay |
| опасно, мало HP | dangerous, low HP |
| критично | critical |

## 9. COMBAT MENU (sensory.py)
| Cyrillic | English |
|----------|---------|
| атаковать | attack |
| блокировать | block |
| бежать | flee |
| кастовать | cast |
| Противник: | Enemy: |
| Твой ход. | Your turn. |
| Мёртв | Dead |

## 10. LOOP MESSAGES (loop.py)
| Cyrillic | English |
|----------|---------|
| Не удалось пройти {dir}. Микро-событие: {t}. Получено {d} урона. | Failed to move {dir}. Micro-event: {t}. Took {d} damage. |
| Не удалось пройти {dir}. Микро-событие: {t}. | Failed to move {dir}. Micro-event: {t}. |
| Ошибка: нет микро-локации | Error: no micro-location |
| Ошибка: {msg} | Error: {msg} |

## 11. LLM CLIENT (llm_client.py)
| Cyrillic | English |
|----------|---------|
| Тьма поглощает. Ты не помнишь куда шёл. | Darkness consumes. You don't remember where you were going. |

## 12. PROMPTS (prompts.py)
All system prompts replaced with English equivalents.

## 13. COMMENTS
Comments left as-is unless they contain game terminology.