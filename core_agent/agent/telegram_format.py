"""
Strike Tips — Shared Telegram Formatter
Converts markdown/text to Telegram-safe HTML, formats race cards into monospace tables,
and handles paragraph-boundary chunking to prevent parse entity crashes and truncation.
"""

import re
from typing import List, Tuple, Optional


def escape_html(text: str) -> str:
    """Escape HTML reserved characters for Telegram HTML mode."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def markdown_to_telegram_html(text: str) -> str:
    """
    Convert Markdown syntax to Telegram-compatible HTML.
    Supports code blocks, inline code, bold, italic, blockquotes, headers, and bullet lists.
    Safely escapes raw text so Telegram never crashes with 'Can't parse entities'.
    """
    if not text:
        return ""

    # 1. Protect code blocks ```lang\ncode```
    code_blocks: List[str] = []
    def _save_code_block(match: re.Match) -> str:
        code_content = match.group(1) if match.group(1) is not None else ""
        escaped_code = escape_html(code_content.strip())
        code_blocks.append(f"<pre>{escaped_code}</pre>")
        return f"___CODE_BLOCK_{len(code_blocks) - 1}___"

    # Pattern for triple backticks with optional language
    text = re.sub(r"```(?:\w+)?\n?(.*?)```", _save_code_block, text, flags=re.DOTALL)

    # 2. Protect inline code `code`
    inline_codes: List[str] = []
    def _save_inline_code(match: re.Match) -> str:
        code_content = match.group(1)
        escaped_code = escape_html(code_content)
        inline_codes.append(f"<code>{escaped_code}</code>")
        return f"___INLINE_CODE_{len(inline_codes) - 1}___"

    text = re.sub(r"`([^`\n]+)`", _save_inline_code, text)

    # Process line-by-line for block elements (headers, blockquotes, bullets)
    lines = text.split("\n")
    processed_lines: List[str] = []
    in_blockquote = False
    blockquote_lines: List[str] = []

    def _flush_blockquote():
        nonlocal in_blockquote, blockquote_lines
        if blockquote_lines:
            content = "\n".join(blockquote_lines)
            processed_lines.append(f"<blockquote>{content}</blockquote>")
            blockquote_lines = []
        in_blockquote = False

    for line in lines:
        stripped = line.strip()

        # Handle blockquotes (lines starting with >)
        if stripped.startswith(">"):
            in_blockquote = True
            bq_text = stripped.lstrip(">").strip()
            blockquote_lines.append(_format_line_inline(bq_text))
            continue
        elif in_blockquote:
            _flush_blockquote()

        # Headers (#, ##, ###) -> Bold line
        if stripped.startswith("#"):
            h_text = re.sub(r"^#+\s*", "", stripped)
            processed_lines.append(f"<b>{_format_line_inline(h_text)}</b>")
            continue

        # Bullet items (*, -, +) -> ▸
        if re.match(r"^[\*\-\+]\s+", stripped):
            b_text = re.sub(r"^[\*\-\+]\s+", "", stripped)
            processed_lines.append(f"▸ {_format_line_inline(b_text)}")
            continue

        # Normal line
        processed_lines.append(_format_line_inline(line))

    if in_blockquote:
        _flush_blockquote()

    result = "\n".join(processed_lines)

    # Restore inline code and code blocks
    for idx, code_html in enumerate(inline_codes):
        result = result.replace(f"___INLINE_CODE_{idx}___", code_html)

    for idx, code_html in enumerate(code_blocks):
        result = result.replace(f"___CODE_BLOCK_{idx}___", code_html)

    return result


def _format_line_inline(line: str) -> str:
    """Format inline markdown elements (bold, italic) on a line while escaping text."""
    if not line:
        return ""

    # Split line by potential placeholders or format markers
    # 1. Escape HTML special characters on non-tag text first
    # We will use tokenization to escape raw text and preserve markdown formatting
    tokens: List[Tuple[str, str]] = []  # (type, content)

    # Convert markdown bold **text** or *text* -> <b>text</b>
    # Convert markdown italic _text_ -> <i>text</i>

    # Tokenize line into parts
    # Match placeholders first so they aren't corrupted
    parts = re.split(r"(___(?:CODE_BLOCK|INLINE_CODE)_\d+___)", line)
    formatted_parts = []

    for part in parts:
        if re.match(r"___(?:CODE_BLOCK|INLINE_CODE)_\d+___", part):
            formatted_parts.append(part)
        else:
            # Escape HTML characters first
            escaped = escape_html(part)

            # Bold **text**
            escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)

            # Bold *text* (when not inside word)
            escaped = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<b>\1</b>", escaped)

            # Italic _text_ (when not inside word)
            escaped = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<i>\1</i>", escaped)

            formatted_parts.append(escaped)

    return "".join(formatted_parts)


def format_race_card_for_telegram(text: str) -> str:
    """
    Detect if text contains a race card and format runner listings into a clean
    monospace <pre> alignment table with emoji headers for Telegram HUD styling.
    """
    if not text or not isinstance(text, str):
        return markdown_to_telegram_html(text)

    # Check for race card indicators
    has_card_header = bool(re.search(r"(?:Course|Track|Race\s+\d+|Off Time:)", text, re.IGNORECASE))
    has_runners = len(re.findall(r"\b\d+[\.\)]\s+[A-Za-z0-9'\s]+[\—\-\|]\s*(?:\d+\.\d+|\b[0-9/]+\b)", text)) >= 2

    if not (has_card_header or has_runners):
        return markdown_to_telegram_html(text)

    lines = text.strip().split("\n")
    header_lines = []
    runner_items = []
    footer_lines = []

    # Regex patterns for runner details
    # E.g.: 1. Thunder Cat — 7.50 — Form: 1-2-3 — J: A. Smith / T: B. Jones
    runner_pattern = re.compile(
        r"^(?P<num>\d+)[\.\)]\s+(?P<name>[^—\-\|]+?)(?:\s*[\—\-\|]\s*(?P<odds>\d+(?:\.\d+)?))?"
        r"(?:\s*[\—\-\|]\s*(?:Form:?\s*)?(?P<form>[0-9xX\-]+))?"
        r"(?:\s*[\—\-\|]\s*(?P<jt>(?:J|T|J\s*/\s*T)?:?.*))?$"
    )

    # Parse course/track/race info
    course = ""
    race_num = ""
    off_time = ""

    for line in lines:
        l_str = line.strip()
        if not l_str:
            continue

        m_course = re.search(r"(?:Course|Track):\s*([^\|]+)", l_str, re.IGNORECASE)
        m_race = re.search(r"Race\s*(\d+)", l_str, re.IGNORECASE)
        m_time = re.search(r"(?:Off Time|Time):\s*([\d:]+)", l_str, re.IGNORECASE)

        if m_course:
            course = m_course.group(1).strip()
        if m_race:
            race_num = m_race.group(1).strip()
        if m_time:
            off_time = m_time.group(1).strip()

        m_runner = runner_pattern.match(l_str)
        if m_runner:
            num = m_runner.group("num")
            name = m_runner.group("name").strip()
            odds = m_runner.group("odds") or ""
            form = m_runner.group("form") or ""
            jt = m_runner.group("jt") or ""
            runner_items.append({
                "num": num,
                "name": name,
                "odds": odds,
                "form": form,
                "jt": jt.strip(),
            })
        elif not runner_items:
            header_lines.append(l_str)
        else:
            footer_lines.append(l_str)

    if not runner_items:
        return markdown_to_telegram_html(text)

    # Build Header
    track_title = escape_html(course.title() if course else "Race Card")
    r_str = f"R{race_num}" if race_num else ""
    t_str = f"⏰ {off_time}" if off_time else ""

    header_parts = ["🏇 <b>" + track_title + "</b>"]
    if r_str:
        header_parts.append(r_str)
    if t_str:
        header_parts.append(t_str)

    formatted_header = " · ".join(header_parts)

    # Format Monospace Table
    max_name_len = max(len(r["name"]) for r in runner_items) if runner_items else 10
    max_name_len = min(max(max_name_len, 10), 16)  # Cap for mobile width

    table_lines = []
    table_lines.append(f"{'#':<2} {'Horse':<{max_name_len}} {'Odds':<6} {'Form'}")
    table_lines.append("-" * (max_name_len + 16))

    for r in runner_items:
        num = r["num"]
        name = r["name"][:max_name_len]
        odds = f"{float(r['odds']):.2f}" if r["odds"] else "-"
        form = r["form"] or "-"
        table_lines.append(f"{num:<2} {name:<{max_name_len}} {odds:<6} {form}")

    table_block = "<pre>" + escape_html("\n".join(table_lines)) + "</pre>"

    result_parts = [formatted_header, table_block]

    if footer_lines:
        footer_text = "\n".join(footer_lines)
        result_parts.append(markdown_to_telegram_html(footer_text))

    return "\n\n".join(result_parts)


def split_for_telegram(text: str, max_length: int = 3800) -> List[str]:
    """
    Split long text at paragraph or line boundaries to fit Telegram's length limits.
    Default max_length is 3800 to leave headroom for HTML tag expansions.
    """
    if not text:
        return []

    if len(text) <= max_length:
        return [text]

    chunks: List[str] = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for p in paragraphs:
        # If adding paragraph fits in current chunk
        if len(current_chunk) + len(p) + 2 <= max_length:
            if current_chunk:
                current_chunk += "\n\n" + p
            else:
                current_chunk = p
        else:
            # Flush existing chunk
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # If the paragraph itself is larger than max_length, split by line
            if len(p) > max_length:
                lines = p.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 <= max_length:
                        if current_chunk:
                            current_chunk += "\n" + line
                        else:
                            current_chunk = line
                    else:
                        if current_chunk:
                            chunks.append(current_chunk)
                            current_chunk = ""

                        # If a single line is still > max_length, hard-cut it
                        if len(line) > max_length:
                            for i in range(0, len(line), max_length):
                                chunks.append(line[i : i + max_length])
                        else:
                            current_chunk = line
            else:
                current_chunk = p

    if current_chunk:
        chunks.append(current_chunk)

    return chunks
