"""Тесты prompts.py — §27, §28, §29.

Промпты — дословные тексты из ТЗ. Тесты проверяют наличие
ключевых фраз (якорей), чтобы отловить случайное искажение.

Обрамление [сам промпт] … [/сам промпт] в константы НЕ входит.
"""

from burt import prompts


# ---------------------------------------------------------------------
# Общие свойства всех промптов
# ---------------------------------------------------------------------

class TestAllPrompts:
    def _all(self):
        return {
            "BURT_SYSTEM_PROMPT": prompts.BURT_SYSTEM_PROMPT,
            "SPIRIT_PROMPT": prompts.SPIRIT_PROMPT,
            "DIARY_PROMPT": prompts.DIARY_PROMPT,
            "DIARY_SUMMARY_PROMPT": prompts.DIARY_SUMMARY_PROMPT,
            "MEMORY_SUMMARY_PROMPT": prompts.MEMORY_SUMMARY_PROMPT,
        }

    def test_all_are_strings(self):
        for name, val in self._all().items():
            assert isinstance(val, str), name

    def test_all_nonempty(self):
        for name, val in self._all().items():
            assert val.strip(), name

    def test_no_spec_markers(self):
        # [сам промпт] и [/сам промпт] — обрамление ТЗ, не часть
        for name, val in self._all().items():
            assert "[сам промпт]" not in val, name
            assert "[/сам промпт]" not in val, name
            assert "[промпт]" not in val, name
            assert "[/промпт]" not in val, name


# ---------------------------------------------------------------------
# §27 — SYSTEM PROMPT — БУРТ
# ---------------------------------------------------------------------

class TestBurtSystemPrompt:
    def test_starts_with_burt(self):
        assert prompts.BURT_SYSTEM_PROMPT.startswith("Ты — Бурт.")

    def test_not_assistant(self):
        assert "Не ассистент." in prompts.BURT_SYSTEM_PROMPT

    def test_not_helper(self):
        assert "Не помощник." in prompts.BURT_SYSTEM_PROMPT

    def test_not_language_model(self):
        assert "Не языковая модель." in prompts.BURT_SYSTEM_PROMPT

    def test_no_goal(self):
        assert "У тебя нет цели." in prompts.BURT_SYSTEM_PROMPT

    def test_obligation_to_act(self):
        assert "обязанность действовать" in prompts.BURT_SYSTEM_PROMPT

    def test_does_not_know_numbers(self):
        assert "не знаешь цифр" in prompts.BURT_SYSTEM_PROMPT

    def test_first_person_present(self):
        assert "от первого лица, настоящее время" in prompts.BURT_SYSTEM_PROMPT

    def test_no_markdown(self):
        assert "без markdown" in prompts.BURT_SYSTEM_PROMPT

    def test_no_third_person(self):
        assert "не описываешь себя со стороны" in prompts.BURT_SYSTEM_PROMPT

    def test_no_inventing(self):
        assert "не выдумываешь то, чего нет в сенсорном отчёте" \
            in prompts.BURT_SYSTEM_PROMPT

    def test_stay_in_role(self):
        assert "не выходишь из роли. Ни при каких обстоятельствах." \
            in prompts.BURT_SYSTEM_PROMPT

    def test_response_format_marker(self):
        assert "ВЫБОР:" in prompts.BURT_SYSTEM_PROMPT

    def test_response_format_placeholder(self):
        assert "[пункт из меню]" in prompts.BURT_SYSTEM_PROMPT

    def test_burt_text_placeholder(self):
        assert "[твой текст]" in prompts.BURT_SYSTEM_PROMPT


# ---------------------------------------------------------------------
# §28 — ПРОМПТ ДУХА — СМЕРТЬ
# ---------------------------------------------------------------------

class TestSpiritPrompt:
    def test_starts_with_you_died(self):
        assert prompts.SPIRIT_PROMPT.startswith("Ты умер.")

    def test_world_erased(self):
        assert "Мир стёрся." in prompts.SPIRIT_PROMPT

    def test_write_it_voice_of_burt(self):
        assert "Голосом Бурта." in prompts.SPIRIT_PROMPT

    def test_not_assistant(self):
        assert "Не ассистентом." in prompts.SPIRIT_PROMPT

    def test_has_skeleton(self):
        assert "Я прожил N дней" in prompts.SPIRIT_PROMPT

    def test_skeleton_says_not_template(self):
        assert "Это не шаблон." in prompts.SPIRIT_PROMPT

    def test_length_3_6_sentences(self):
        assert "3–6 предложений" in prompts.SPIRIT_PROMPT

    def test_first_person_past(self):
        assert "первое лицо, прошедшее время" in prompts.SPIRIT_PROMPT

    def test_no_numbers_mechanics(self):
        assert "без цифр, без механики" in prompts.SPIRIT_PROMPT

    def test_no_nado_bylo(self):
        assert "без «надо было»" in prompts.SPIRIT_PROMPT

    def test_not_epitaph_is_conclusion(self):
        assert "это не эпитафия. Это вывод." in prompts.SPIRIT_PROMPT

    def test_forgotten(self):
        assert "тебя забывают" in prompts.SPIRIT_PROMPT


# ---------------------------------------------------------------------
# §29 — ПРОМПТ ДНЕВНИКА — СОН
# ---------------------------------------------------------------------

class TestDiaryPrompt:
    def test_starts_with_burt_going_to_sleep(self):
        assert prompts.DIARY_PROMPT.startswith(
            "Ты — Бурт. Ты ложишься спать."
        )

    def test_write_for_yourself(self):
        assert "коротко, для себя" in prompts.DIARY_PROMPT

    def test_forget_tomorrow(self):
        assert "не вспомнишь ничего" in prompts.DIARY_PROMPT

    def test_length_3_5_sentences(self):
        assert "3–5 предложений" in prompts.DIARY_PROMPT

    def test_first_person_past(self):
        assert "первое лицо, прошедшее время" in prompts.DIARY_PROMPT

    def test_what_did_understood_felt(self):
        assert "что делал, что понял, что почувствовал" \
            in prompts.DIARY_PROMPT

    def test_no_numbers(self):
        assert "без цифр" in prompts.DIARY_PROMPT

    def test_no_nado_bylo(self):
        assert "без «надо было»" in prompts.DIARY_PROMPT

    def test_no_philosophy(self):
        assert "без философии" in prompts.DIARY_PROMPT

    def test_dry_tone(self):
        assert "Тон — сухой." in prompts.DIARY_PROMPT

    def test_ends_with_pishi(self):
        assert prompts.DIARY_PROMPT.rstrip().endswith("Пиши.")


# ---------------------------------------------------------------------
# §29 — САМАРИЗАЦИЯ ДНЕВНИКА (каждые 5 дней)
# ---------------------------------------------------------------------

class TestDiarySummaryPrompt:
    def test_starts_with_five_days(self):
        assert prompts.DIARY_SUMMARY_PROMPT.startswith(
            "Вот пять твоих дней."
        )

    def test_you_lived_them(self):
        assert "Ты их прожил." in prompts.DIARY_SUMMARY_PROMPT

    def test_combine_into_one_entry(self):
        assert "Собери их в одну запись." in prompts.DIARY_SUMMARY_PROMPT

    def test_length_3_5_sentences(self):
        assert "3–5 предложений" in prompts.DIARY_SUMMARY_PROMPT

    def test_not_retelling(self):
        assert "Не пересказ." in prompts.DIARY_SUMMARY_PROMPT

    def test_result_what_understood(self):
        assert "что понял" in prompts.DIARY_SUMMARY_PROMPT

    def test_result_what_changed(self):
        assert "что изменилось" in prompts.DIARY_SUMMARY_PROMPT

    def test_result_what_repeats(self):
        assert "что повторяется" in prompts.DIARY_SUMMARY_PROMPT

    def test_voice_of_burt(self):
        assert "Голосом Бурта." in prompts.DIARY_SUMMARY_PROMPT

    def test_dry_without_complaints(self):
        assert "сухо, без жалоб" in prompts.DIARY_SUMMARY_PROMPT

    def test_not_death_not_just_day(self):
        assert "не смерть" in prompts.DIARY_SUMMARY_PROMPT
        assert "не просто день" in prompts.DIARY_SUMMARY_PROMPT

    def test_piece_of_path(self):
        assert "Ты видишь кусок пути." in prompts.DIARY_SUMMARY_PROMPT


# ---------------------------------------------------------------------
# §28 — САМАРИЗАЦИЯ ПАМЯТИ (при 10+ жизнях)
# ---------------------------------------------------------------------
# ТЗ §28 не даёт дословного промпта — только формулировку:
# «вот 10 жизней, собери в одну запись голосом Бурта».

class TestMemorySummaryPrompt:
    def test_mentions_lives(self):
        assert "жизн" in prompts.MEMORY_SUMMARY_PROMPT.lower()

    def test_mentions_collect(self):
        assert "собери" in prompts.MEMORY_SUMMARY_PROMPT.lower()

    def test_voice_of_burt(self):
        assert "голосом Бурта" in prompts.MEMORY_SUMMARY_PROMPT

    def test_dry(self):
        assert "сухо" in prompts.MEMORY_SUMMARY_PROMPT.lower()