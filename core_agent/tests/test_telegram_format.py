"""
Tests for Telegram Shared Formatter & Integration Pins
Verifies HTML escaping, Markdown conversion, Race Card table formatting, text splitting,
and source-pin wiring in modal_app.py and channels/telegram.py.
"""

import pytest
from core_agent.agent.telegram_format import (
    escape_html,
    markdown_to_telegram_html,
    format_race_card_for_telegram,
    split_for_telegram,
)


def test_escape_html():
    assert escape_html("A & B < C > D") == "A &amp; B &lt; C &gt; D"
    assert escape_html("") == ""
    assert escape_html(None) == ""


def test_markdown_to_telegram_html_basic():
    md = "# Overview\n**Bold text** and *italic* or _italic_ and `code_snippet`\n- Item 1\n- Item 2"
    html = markdown_to_telegram_html(md)
    assert "<b>Overview</b>" in html
    assert "<b>Bold text</b>" in html
    assert "<code>code_snippet</code>" in html
    assert "▸ Item 1" in html
    assert "▸ Item 2" in html


def test_markdown_to_telegram_html_unbalanced_never_crashes():
    # Unbalanced stars, apostrophes, underscores e.g. "Sascha's Dream *odds 7.50"
    unbalanced = "Horse Sascha's Dream *odds 7.50_ not closed `unclosed code"
    # Must run clean without raising exception
    html = markdown_to_telegram_html(unbalanced)
    assert isinstance(html, str)
    assert "Sascha&apos;s" not in html  # Standard raw quotes remain, HTML entities escaped
    assert "Sascha" in html


def test_markdown_to_telegram_html_code_blocks_and_quotes():
    md = "> Useful quote\n```python\ndef test():\n    return True\n```"
    html = markdown_to_telegram_html(md)
    assert "<blockquote>Useful quote</blockquote>" in html
    assert "<pre>def test():\n    return True</pre>" in html


def test_format_race_card_greyville_card():
    sample_card = (
        "Course: Greyville | Race 8 | Off Time: 15:15\n"
        "1. Thunder Cat — 7.50 — Form: 1-2-3 — J: A. Smith / T: B. Jones\n"
        "2. Silver Blade — 12.00 — Form: 3-4-1 — J: C. D / T: E. F\n"
        "3. Golden Arrow — 4.20 — Form: 1-1-2 — J: G. H / T: I. J\n"
        "4. Royal Dash — 8.00 — Form: 2-3-5 — J: K. L / T: M. N\n"
        "5. Storm Chaser — 15.00 — Form: 5-6-4 — J: O. P / T: Q. R\n"
        "6. Wild Fire — 6.50 — Form: 2-1-1 — J: S. T / T: U. V\n"
        "7. Night Rider — 9.00 — Form: 4-2-3 — J: W. X / T: Y. Z\n"
        "8. Solar Eclipse — 11.00 — Form: 1-5-2 — J: A. B / T: C. D\n"
        "9. Star Light — 14.00 — Form: 6-3-2 — J: E. F / T: G. H\n"
        "10. Velvet Glove — 5.00 — Form: 1-3-1 — J: I. J / T: K. L"
    )

    formatted = format_race_card_for_telegram(sample_card)
    assert "🏇 <b>Greyville</b>" in formatted
    assert "R8" in formatted
    assert "⏰ 15:15" in formatted
    assert "<pre>" in formatted
    assert "</pre>" in formatted
    assert "Thunder Cat" in formatted
    assert "7.50" in formatted
    assert "Velvet Glove" in formatted
    assert "5.00" in formatted


def test_split_for_telegram_paragraphs():
    p1 = "Paragraph 1 " * 100
    p2 = "Paragraph 2 " * 100
    full_text = f"{p1}\n\n{p2}"

    chunks = split_for_telegram(full_text, max_length=1200)
    assert len(chunks) == 2
    assert "Paragraph 1" in chunks[0]
    assert "Paragraph 2" in chunks[1]


def test_split_for_telegram_hard_cut():
    long_line = "A" * 5000
    chunks = split_for_telegram(long_line, max_length=2000)
    assert len(chunks) == 3
    assert len(chunks[0]) == 2000
    assert len(chunks[1]) == 2000
    assert len(chunks[2]) == 1000


def test_source_pins_telegram_format():
    """Verify that modal_app.py and channels/telegram.py import and use telegram_format."""
    import inspect
    from core_agent.core import modal_app
    from core_agent.channels import telegram as telegram_channel

    modal_src = inspect.getsource(modal_app)
    channel_src = inspect.getsource(telegram_channel)

    # Check typing indicator loop in modal_app
    assert "send_chat_action" in modal_src or "typing" in modal_src
    assert "markdown_to_telegram_html" in modal_src or "telegram_format" in modal_src

    # Check formatting and typing in channels/telegram.py
    assert "markdown_to_telegram_html" in channel_src or "telegram_format" in channel_src
