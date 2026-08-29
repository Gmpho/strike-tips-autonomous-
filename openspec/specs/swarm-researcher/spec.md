# swarm-researcher Specification

## Purpose
Autonomously guarantees a form insight for every runner in every region and ingests real racing news, so operators and downstream RAG consumers never see blank commentary regardless of whether Betway publishes Timeform prose.

## Requirements

### Requirement: Region detection for every race event
The system SHALL detect and assign a region for every race event derived from the Betway snapshot.

#### Scenario: Region derived from display prefix
- **WHEN** an event has `en` starting with `"USA: Saratoga"`
- **THEN** the detected region is `"USA"`

#### Scenario: Region fallback via course keyword
- **WHEN** an event's `en` prefix is missing or unknown and `course` contains `"Turffontein"`
- **THEN** the detected region is `"South Africa"`

#### Scenario: Unknown region default
- **WHEN** neither prefix nor course keyword matches any known region
- **THEN** the detected region is `"Unknown"`

### Requirement: Deterministic field blurb for runners missing timeForm
The system SHALL generate a deterministic, zero-cost field blurb for every runner whose `timeForm` is empty, using only live runner fields.

#### Scenario: Blurb contains live fields
- **WHEN** a runner missing `timeForm` has `form="123", draw=5, age="3yo", weight="9st 7lbs"`
- **THEN** the generated blurb contains `form 123`, `draw 5`, `3yo`, and `9st 7lbs`

#### Scenario: Blurb never fabricates
- **WHEN** a runner has no `form`, no `draw`, and no `age/weight`
- **THEN** the blurb still returns a non-empty string without inventing performance claims

#### Scenario: Snapshot enrichment always runs
- **WHEN** the monitor finishes building a snapshot for the current cycle
- **THEN** every runner missing `timeForm` receives `region`, `swarmInsight`, and `insightSource` before `set_snapshot` is called

### Requirement: Gated web-grounded AI upgrade for priority runners
The system SHALL only perform web search and Groq summarisation for priority runners and SHALL enforce strict budget caps.

#### Scenario: Priority gate
- **WHEN** a runner is in `aiSelections`, is a market mover, or has `odds ≤ 6.0`
- **THEN** it is eligible for web-grounded upgrade; other runners receive only the field blurb

#### Scenario: Groq budget cap
- **WHEN** more than 6 priority runners are eligible in a single cycle
- **THEN** at most 6 Groq calls are issued in that cycle

#### Scenario: Per-horse per-day cache
- **WHEN** a horse already has a web-grounded insight for today cached by horse+date
- **THEN** no new Groq call is issued for that horse until the next day

#### Scenario: Fallback on AI failure
- **WHEN** web search returns no results or Groq returns empty
- **THEN** the runner retains its deterministic field blurb without error

### Requirement: RSS news polling and deduplication
The system SHALL poll free RSS news feeds on a fixed schedule, normalise, dedupe by link, cap, and atomically persist the result.

#### Scenario: Poll produces capped deduped file
- **WHEN** the 10-minute poll fetches items from BBC Sport, Guardian and Mirror feeds containing duplicate links
- **THEN** `data/news_latest.json` contains at most 50 items with no duplicate `url` values, written atomically (tmp + rename)

#### Scenario: No LLM cost on news path
- **WHEN** news items are polled and stored
- **THEN** no Groq/LLM call is issued for headline or summary storage

### Requirement: ChromaDB persistence and freshness gating
The system SHALL persist racing insights to ChromaDB `form_insights` and SHALL skip re-persisting insights for horses that already have today's insight.

#### Scenario: Insight persisted with required metadata
- **WHEN** a field blurb or web-grounded summary is generated for a horse on a given date
- **THEN** a document is upserted into `form_insights` with `type:"racing_insight"`, `region`, `source` (`field_only` or `web` or `news`), and `ts`

#### Scenario: Freshness gate skips duplicates
- **WHEN** a horse already has a `racing_insight` for today in ChromaDB for the same region
- **THEN** no new document is written for that horse until the next day and an agent note is not duplicated

#### Scenario: Agent note appended
- **WHEN** a new `racing_insight` is successfully persisted
- **THEN** an agent note of the form `[<date>] Racing insight saved (<region>/<source>): <horse>` is appended to curated memory

### Requirement: News linking is pure and caller-controlled
The system SHALL provide a pure news-to-snapshot linking function whose persistence is caller-controlled.

#### Scenario: Stateless linking without seen file
- **WHEN** `_link_news_to_insights` is called with items matching a live snapshot horse and no `seen_path`
- **THEN** it returns the count of linked stories without writing any file

#### Scenario: Dedupe via seen_path in production
- **WHEN** `_link_news_to_insights` is called twice with the same items and the same `seen_path`
- **THEN** the first call links the stories and persists their ids, and the second call returns 0

#### Scenario: Short horse names are not matched spuriously
- **WHEN** a snapshot horse name is shorter than 5 characters
- **THEN** it SHALL NOT trigger a substring match against news text

### Requirement: Swarm loop scheduling
The system SHALL run the swarm researcher as a continuous background loop alongside the existing heartbeat loop without blocking the odds monitor.

#### Scenario: Loops coexist
- **WHEN** `AdaptiveOddsMonitor` starts
- **THEN** both `run_heartbeat_loop` and `run_swarm_loop(interval=600)` are scheduled as independent asyncio tasks and the monitor `sleep` interval is unchanged

#### Scenario: Poll news independently
- **WHEN** the swarm loop ticks
- **THEN** it performs form backfill if a snapshot exists and polls news regardless of snapshot presence
