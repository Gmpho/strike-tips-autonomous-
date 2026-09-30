# Capability: telegram-openclaw-style

## Purpose

Telegram answers behave like a trackside pundit in OpenClaw's formatting
contract: snapshot only when the turn is about racing, web search when
asked, data always as scannable ASCII tables.

## ADDED Requirements

### Requirement: Search intent suppresses the card

Messages asking for web search SHALL NOT receive the live snapshot, and
the agent SHALL call `search_racing_data` for them.

#### Scenario: Explicit web search
- **WHEN** the user writes "search the web for Kenilworth results"
- **THEN** `wants_live_card` returns False and the turn carries a
  search flag instead of snapshot context

#### Scenario: Generic nouns stay conversational
- **WHEN** the user writes "that bet was close" (no track, horse, odds,
  or race number)
- **THEN** `wants_live_card` returns False

### Requirement: Tables render as monospace blocks

Markdown pipe tables in replies SHALL be converted to `<pre>` ASCII
tables before chunking, preserving alignment and surviving splits.

#### Scenario: Pipe table conversion
- **WHEN** a reply contains a `| Horse | Odds |` table
- **THEN** Telegram shows a monospace block, not literal pipes

### Requirement: Compact default, full on demand

Data tables SHALL default to Horse|Odds|Edge columns; the full
draw/gear/days/pedigree set renders only on explicit "full", remembered
per session.

#### Scenario: Full keyword
- **WHEN** the user replies "full" after a compact table
- **THEN** the same race re-renders with all columns
