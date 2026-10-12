"""Тесты для config.py.

Разделы ТЗ: §3 (время), §4 (голод), §17 (локации),
§24-25 (отображение), §28 (память), §31 (конфиг), §39 (логи).

Настройки LLM (BACKEND, URL, MODEL, TEMPERATURE) НЕ тестируются —
это крутилки, не жёсткие требования.
"""

import config


# ---------------------------------------------------------------------
# DISPLAY (§31, §24, §25)
# ---------------------------------------------------------------------

class TestDisplay:
    def test_hp_display_is_numbers(self):
        # §24, §31
        assert config.HP_DISPLAY == "numbers"

    def test_show_hunger_timer_is_false(self):
        # §25: голод показывается качественно, не счётчиком
        assert config.SHOW_HUNGER_TIMER is False

    def test_show_sleep_timer_is_true(self):
        # §25: сон показывается счётчиком
        assert config.SHOW_SLEEP_TIMER is True

    def test_show_date_is_true(self):
        assert config.SHOW_DATE is True


# ---------------------------------------------------------------------
# TIME (§3, §31)
# ---------------------------------------------------------------------

class TestTime:
    def test_day_steps(self):
        # §3: DAY_STEPS = 20
        assert config.DAY_STEPS == 20


# ---------------------------------------------------------------------
# HUNGER (§4, §31)
# ---------------------------------------------------------------------

class TestHunger:
    def test_hungry_at(self):
        # §4: HUNGER_HUNGRY_AT = [0, 10]
        assert config.HUNGER_HUNGRY_AT == [0, 10]

    def test_death_at(self):
        # §4: HUNGER_DEATH_AT = [8, 18]
        assert config.HUNGER_DEATH_AT == [8, 18]

    def test_death_after_hungry(self):
        # Смерть наступает ПОСЛЕ инжекта голода
        for hungry, death in zip(
            config.HUNGER_HUNGRY_AT, config.HUNGER_DEATH_AT
        ):
            assert death > hungry

    def test_death_within_day(self):
        # Смерть укладывается в день
        for death in config.HUNGER_DEATH_AT:
            assert death < config.DAY_STEPS

    def test_hungry_and_death_same_length(self):
        assert len(config.HUNGER_HUNGRY_AT) == len(config.HUNGER_DEATH_AT)


# ---------------------------------------------------------------------
# LOCATIONS (§17) — вынесено из world.py, долг В7
# ---------------------------------------------------------------------

class TestLocations:
    def test_location_types_is_frozenset(self):
        assert isinstance(config.LOCATION_TYPES, frozenset)

    def test_location_types_has_11_entries(self):
        # старт, кустарник, лес, поле, степь, болото, река, дорога,
        # деревня, храм, подземелье
        assert len(config.LOCATION_TYPES) == 11

    def test_location_types_full_set(self):
        assert config.LOCATION_TYPES == {
            "старт", "кустарник",
            "лес", "поле", "степь", "болото", "река", "дорога",
            "деревня", "храм", "подземелье",
        }

    def test_rolls_table_covers_1_to_6(self):
        assert set(config.LOCATION_TYPE_ROLLS.keys()) == {1, 2, 3, 4, 5, 6}

    def test_roll_1_and_2_forest(self):
        assert config.LOCATION_TYPE_ROLLS[1] == "лес"
        assert config.LOCATION_TYPE_ROLLS[2] == "лес"

    def test_roll_3_field(self):
        assert config.LOCATION_TYPE_ROLLS[3] == "поле"

    def test_roll_4_steppe(self):
        assert config.LOCATION_TYPE_ROLLS[4] == "степь"

    def test_roll_5_tuple(self):
        # roll=5 → уточняющий 1d3
        assert config.LOCATION_TYPE_ROLLS[5] == (
            "болото", "река", "дорога",
        )

    def test_roll_6_tuple(self):
        # roll=6 → уточняющий 1d6
        assert config.LOCATION_TYPE_ROLLS[6] == (
            "храм", "подземелье",
            "деревня", "деревня", "деревня", "деревня",
        )

    def test_rolls_values_are_known_types(self):
        # каждое значение таблицы входит в LOCATION_TYPES
        for entry in config.LOCATION_TYPE_ROLLS.values():
            values = (entry,) if isinstance(entry, str) else entry
            for v in values:
                assert v in config.LOCATION_TYPES

    def test_start_and_bush_never_roll(self):
        # "старт" и "кустарник" не выпадают в roll_location_type
        for entry in config.LOCATION_TYPE_ROLLS.values():
            values = (entry,) if isinstance(entry, str) else entry
            assert "старт" not in values
            assert "кустарник" not in values


# ---------------------------------------------------------------------
# MEMORY (§28, §31)
# ---------------------------------------------------------------------

class TestMemory:
    def test_memory_compress_at(self):
        # §28: самаризация при 10+ жизнях
        assert config.MEMORY_COMPRESS_AT == 10


# ---------------------------------------------------------------------
# LOGGING (§31, §38, §39)
# ---------------------------------------------------------------------

class TestLogging:
    def test_debug_is_bool(self):
        assert isinstance(config.DEBUG, bool)

    def test_log_level_in_spec_range(self):
        # §39: уровни 0..3
        assert config.LOG_LEVEL in (0, 1, 2, 3)

    def test_log_dir_is_string(self):
        assert isinstance(config.LOG_DIR, str)
        assert config.LOG_DIR

    def test_crash_dir_is_string(self):
        assert isinstance(config.CRASH_DIR, str)
        assert config.CRASH_DIR

    def test_log_rotate_hours(self):
        # §39: ротация каждые 12 часов
        assert config.LOG_ROTATE_HOURS == 12

    def test_ring_buffer_size(self):
        # §39: ring buffer на 20 строк
        assert config.RING_BUFFER_SIZE == 20