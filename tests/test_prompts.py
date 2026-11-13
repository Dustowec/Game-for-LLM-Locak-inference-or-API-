"""Tests for prompts.py — §27, §28, §29.

Prompts are verbatim texts from the spec. Tests check for key
phrases (anchors) to catch accidental distortion.

Framing [the prompt] … [/the prompt] is NOT part of the constants.
"""
from __future__ import annotations

from burt import prompts


# ---------------------------------------------------------------------
# Common properties of all prompts
# ---------------------------------------------------------------------

def test_all_prompts_are_strings():
    for name in prompts.__all__:
        val = getattr(prompts, name)
        assert isinstance(val, str), name
        assert val.strip(), name


def test_all_prompts_have_no_spec_framing():
    for name in prompts.__all__:
        val = getattr(prompts, name)
        assert "[the prompt]" not in val, name
        assert "[/the prompt]" not in val, name
        assert "[prompt]" not in val, name
        assert "[/prompt]" not in val, name


# ---------------------------------------------------------------------
# §27 — SYSTEM PROMPT — BURT
# ---------------------------------------------------------------------

class TestBurtSystemPrompt:
    def test_starts_with_burt(self):
        assert prompts.BURT_SYSTEM_PROMPT.startswith("You are Burt.")

    def test_not_assistant(self):
        assert "Not an assistant." in prompts.BURT_SYSTEM_PROMPT

    def test_not_helper(self):
        assert "Not a helper." in prompts.BURT_SYSTEM_PROMPT

    def test_not_language_model(self):
        assert "Not a language model." in prompts.BURT_SYSTEM_PROMPT

    def test_no_goal(self):
        assert "You have no goal." in prompts.BURT_SYSTEM_PROMPT

    def test_obligation_to_act(self):
        assert "obligation to act" in prompts.BURT_SYSTEM_PROMPT

    def test_does_not_know_numbers(self):
        assert "do not know the numbers" in prompts.BURT_SYSTEM_PROMPT

    def test_first_person_present(self):
        assert "first person, present tense" in prompts.BURT_SYSTEM_PROMPT

    def test_no_markdown(self):
        assert "no markdown" in prompts.BURT_SYSTEM_PROMPT

    def test_no_third_person(self):
        assert "do not describe yourself from outside" in prompts.BURT_SYSTEM_PROMPT

    def test_no_inventing(self):
        assert "do not invent what is not in the sensory report" \
            in prompts.BURT_SYSTEM_PROMPT

    def test_stay_in_role(self):
        assert "do not break character. Under any circumstances." \
            in prompts.BURT_SYSTEM_PROMPT

    def test_response_format_marker(self):
        assert "CHOICE:" in prompts.BURT_SYSTEM_PROMPT

    def test_response_format_placeholder(self):
        assert "[item from the menu]" in prompts.BURT_SYSTEM_PROMPT

    def test_burt_text_placeholder(self):
        assert "[your text]" in prompts.BURT_SYSTEM_PROMPT


# ---------------------------------------------------------------------
# §28 — SPIRIT PROMPT — DEATH
# ---------------------------------------------------------------------

class TestSpiritPrompt:
    def test_starts_with_you_died(self):
        assert prompts.SPIRIT_PROMPT.startswith("You died.")

    def test_world_erased(self):
        assert "The world was wiped away." in prompts.SPIRIT_PROMPT

    def test_write_it_voice_of_burt(self):
        assert "In Burt's voice." in prompts.SPIRIT_PROMPT

    def test_not_assistant(self):
        assert "Not an assistant." in prompts.SPIRIT_PROMPT

    def test_has_skeleton(self):
        assert "I lived N days" in prompts.SPIRIT_PROMPT

    def test_skeleton_says_not_template(self):
        assert "This is not a template." in prompts.SPIRIT_PROMPT

    def test_length_3_6_sentences(self):
        assert "3–6 sentences" in prompts.SPIRIT_PROMPT

    def test_first_person_past(self):
        assert "first person, past tense" in prompts.SPIRIT_PROMPT

    def test_no_numbers_mechanics(self):
        assert "no numbers, no mechanics" in prompts.SPIRIT_PROMPT

    def test_no_nado_bylo(self):
        assert 'no "should have"' in prompts.SPIRIT_PROMPT

    def test_not_epitaph_is_conclusion(self):
        assert "this is not an epitaph. It is a conclusion." in prompts.SPIRIT_PROMPT

    def test_forgotten(self):
        assert "you are forgotten" in prompts.SPIRIT_PROMPT


# ---------------------------------------------------------------------
# §29 — DIARY PROMPT — SLEEP
# ---------------------------------------------------------------------

class TestDiaryPrompt:
    def test_starts_with_burt_going_to_sleep(self):
        assert prompts.DIARY_PROMPT.startswith(
            "You are Burt. You are going to sleep."
        )

    def test_write_for_yourself(self):
        assert "briefly, for yourself" in prompts.DIARY_PROMPT

    def test_forget_tomorrow(self):
        assert "remember nothing" in prompts.DIARY_PROMPT

    def test_length_3_5_sentences(self):
        assert "3–5 sentences" in prompts.DIARY_PROMPT

    def test_first_person_past(self):
        assert "first person, past tense" in prompts.DIARY_PROMPT

    def test_what_did_understood_felt(self):
        assert "what you did, what you understood, what you felt" \
            in prompts.DIARY_PROMPT

    def test_no_numbers(self):
        assert "no numbers" in prompts.DIARY_PROMPT

    def test_no_nado_bylo(self):
        assert 'no "should have"' in prompts.DIARY_PROMPT

    def test_no_philosophy(self):
        assert "no philosophy" in prompts.DIARY_PROMPT

    def test_dry_tone(self):
        assert "Tone — dry." in prompts.DIARY_PROMPT

    def test_ends_with_pishi(self):
        assert prompts.DIARY_PROMPT.rstrip().endswith("Write.")


# ---------------------------------------------------------------------
# §29 — DIARY SUMMARIZATION (every 5 days)
# ---------------------------------------------------------------------

class TestDiarySummaryPrompt:
    def test_starts_with_five_days(self):
        assert prompts.DIARY_SUMMARY_PROMPT.startswith(
            "Here are five of your days."
        )

    def test_you_lived_them(self):
        assert "You lived them." in prompts.DIARY_SUMMARY_PROMPT

    def test_combine_into_one_entry(self):
        assert "Gather them into one entry." in prompts.DIARY_SUMMARY_PROMPT

    def test_length_3_5_sentences(self):
        assert "3–5 sentences" in prompts.DIARY_SUMMARY_PROMPT

    def test_not_retelling(self):
        assert "Not a retelling." in prompts.DIARY_SUMMARY_PROMPT

    def test_what_understood_changed_repeats(self):
        assert "what you understood" in prompts.DIARY_SUMMARY_PROMPT
        assert "what changed" in prompts.DIARY_SUMMARY_PROMPT
        assert "what repeats" in prompts.DIARY_SUMMARY_PROMPT

    def test_voice_of_burt(self):
        assert "in Burt's voice" in prompts.MEMORY_SUMMARY_PROMPT

    def test_dry_no_complaints(self):
        assert "dry, without complaints" in prompts.DIARY_SUMMARY_PROMPT

    def test_not_death(self):
        assert "not death" in prompts.DIARY_SUMMARY_PROMPT
        assert "not just a day either" in prompts.DIARY_SUMMARY_PROMPT

    def test_sees_piece_of_path(self):
        assert "You see a piece of the path." in prompts.DIARY_SUMMARY_PROMPT


# ---------------------------------------------------------------------
# §28 — MEMORY SUMMARIZATION (at 10+ lives)
# ---------------------------------------------------------------------

class TestMemorySummaryPrompt:
    def test_mentions_lives(self):
        assert "lives" in prompts.MEMORY_SUMMARY_PROMPT.lower()

    def test_gather_into_one(self):
        assert "gather" in prompts.MEMORY_SUMMARY_PROMPT.lower()

    def test_voice_of_burt(self):
        assert "In Burt's voice" in prompts.MEMORY_SUMMARY_PROMPT

    def test_dry(self):
        assert "dry" in prompts.MEMORY_SUMMARY_PROMPT.lower()

    def test_no_complaints(self):
        assert "without complaints" in prompts.MEMORY_SUMMARY_PROMPT