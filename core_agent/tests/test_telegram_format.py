"""Grapheme-safe Telegram chunking (Sep-2026: split mid-emoji rendered ��)."""
from core_agent.agent.telegram_format import (
    _split_grapheme_safe,
    _utf16_units,
    split_for_telegram,
)


def _first_bad_boundary(chunks):
    import unicodedata

    bad = []
    for c in chunks:
        if not c:
            continue
        last = c[-1]
        if (unicodedata.category(last) in ("Mn", "Me")
                or last in ("\u200d", "️", "️")
                or 0x1F1E6 <= ord(last) <= 0x1F1FF):
            bad.append(c[-20:])
    return bad


def test_split_never_breaks_emoji():
    text = ("🏇 Firealley holds edge 🇿🇦 family 👨\u200d👩\u200d👧 café 🎯 " * 200).strip()
    chunks = _split_grapheme_safe(text, 3800)
    assert "".join(chunks) == text
    assert _first_bad_boundary(chunks) == []
    for c in chunks:
        assert _utf16_units(c) <= 3800 + 4  # at most one cluster overrun


def test_split_for_telegram_hard_cut_is_emoji_safe():
    line = "A" * 3700 + "👨\u200d👩\u200d👧🇿🇦café" + "B" * 200
    chunks = split_for_telegram(line, max_length=3800)
    assert "".join(chunks) == line
    assert _first_bad_boundary(chunks) == []


def test_utf16_units_counts_astral_double():
    assert _utf16_units("abc") == 3
    assert _utf16_units("🏇") == 2
    assert _utf16_units("🇿🇦") == 4
