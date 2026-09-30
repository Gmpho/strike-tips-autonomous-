"""OpenClaw-style Telegram: search-intent gate, table converter, SOUL voice.

Pins the telegram-openclaw-style change:
  1. "search the web ..." turns skip the card (the months-old bug where the
     snapshot answered every search request),
  2. generic nouns ("that bet was close") stay conversational,
  3. Markdown pipe tables become ```text fenced ASCII tables,
  4. SOUL.md voice + table rule load for Telegram turns only,
  5. bare "full"/"compact" toggles re-render with the card attached.
"""

import pytest

from core_agent.agent.context import (
    wants_live_card,
    wants_search,
    table_mode_request,
)
from core_agent.agent.telegram_format import markdown_table_to_pre


# ── Search intent ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "search the web for Kenilworth results",
    "google today's Durbanville winners",
    "look up the latest SA racing news",
    "what's new in horse racing today",
    "find me news about the July handicap",
])
def test_search_turns_want_search_not_card(text):
    assert wants_search(text) is True
    assert wants_live_card(text) is False, f"search turn got card: {text!r}"


# ── Generic nouns stay conversational ─────────────────────────────────────

@pytest.mark.parametrize("text", [
    "that bet was close",
    "my stake is getting low",
    "no edge in that market",
    "winner stays on?",
    "let's talk betting strategy generally",
])
def test_generic_noun_turns_skip_card(text):
    # None carry track/horse/odds/race refs — no card should attach.
    assert wants_live_card(text) is False, f"casual turn got card: {text!r}"


# ── Racing turns still keep the card ──────────────────────────────────────

@pytest.mark.parametrize("text", [
    "races at turffontein",
    "any value picks today?",
    "Firealley form and odds",
    "R4 greyville runners",
])
def test_racing_turns_keep_card(text):
    assert wants_live_card(text) is True, f"racing turn lost card: {text!r}"


# ── Table-mode toggle ─────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [
    ("full", "full"),
    ("Full", "full"),
    ("full table", "full"),
    ("compact", "compact"),
    ("a full field of runners", None),  # prose, not a toggle
    ("show me the full card", None),    # card request, not a toggle
])
def test_table_mode_request(text, expected):
    assert table_mode_request(text) == expected


# ── Pipe-table converter ──────────────────────────────────────────────────

def test_pipe_table_becomes_fenced_text_block():
    src = (
        "Here are the runners:\n\n"
        "| Horse | Odds | Edge |\n"
        "|---|---|---|\n"
        "| Firealley | 4.50 | +12.4% |\n"
        "| Thunder Cat | 7.00 | +3.1% |\n"
    )
    out = markdown_table_to_pre(src)
    assert "```text" in out
    assert "|---|---|" not in out  # alignment row dropped
    assert "|" not in out.split("```text")[1].split("```")[0]  # no raw pipes
    assert "Firealley" in out and "4.50" in out
    # Header and rows share column alignment
    lines = out.split("```text")[1].split("```")[0].strip().split("\n")
    assert len(lines) == 3


def test_non_table_text_untouched():
    src = "Just a normal message with a | pipe character."
    assert markdown_table_to_pre(src) == src


def test_single_pipe_line_not_a_table():
    src = "| lone row, no table here"
    assert markdown_table_to_pre(src) == src


# ── SOUL + Telegram prompt rules ──────────────────────────────────────────

def test_soul_loads_for_telegram_only():
    from core_agent.agent.prompts import build_system_prompt

    tg = build_system_prompt(for_cloud=True, user_message="races at greyville", channel="telegram")
    assert "trackside" in tg.lower() or "SOUL" in tg or "pundit" in tg.lower()
    assert "Markdown pipe table" in tg

    hud = build_system_prompt(for_cloud=True, user_message="races at greyville", channel="web")
    assert "Markdown pipe table" not in hud


def test_search_rule_present():
    from core_agent.agent.prompts import build_system_prompt

    out = build_system_prompt(for_cloud=True, user_message="search the web for results")
    assert "search_racing_data" in out
    assert "Live race card withheld" in out


@pytest.mark.asyncio
async def test_full_toggle_forces_card_with_history():
    from core_agent.agent.context import ContextBuilder

    cb = ContextBuilder()
    hist = [{"role": "user", "content": "races at greyville"}]
    out = await cb.build("s", "full", hist, None)
    assert "[TABLE MODE: full" in out
