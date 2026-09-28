# Capability: chat-web-search

## Purpose

Live web grounding for the HUD chat served by the metered free-tier edge
cascade (Tavily → Exa → Brave), identical across cloud and browser-local
models, with no Google grounding tool and no paid fallback.

## ADDED Requirements

### Requirement: Cascade is the only chat web-search source

Every chat web-search request SHALL be served by the edge MCP cascade
(`web_search_racing`); the Gemini `googleSearch` grounding tool SHALL NOT be
sent on any chat request.

#### Scenario: Gemini turn with search on
- **WHEN** a chat turn runs with the search toggle enabled on
  `gemini-3.5-flash`
- **THEN** the request carries cascade results as context and no
  `googleSearch` tool is attached

### Requirement: Search applies to every model

The cascade context SHALL be injected for Gemini models, Groq models, and
browser-local WebGPU models alike; no model class SHALL be silently excluded.

#### Scenario: Groq turn with search on
- **WHEN** a Groq-backed chat turn runs with search enabled
- **THEN** the handler receives the same cascade context and returns source
  chips for it

### Requirement: Model-agnostic, mobile-visible control

The Search control SHALL render for every model selection and SHALL present
its visible label at all viewport widths, including viewports below the `sm`
breakpoint.

#### Scenario: Phone with a Groq model selected
- **WHEN** the chat renders on a <640px viewport with a non-Gemini model
  selected in persisted state
- **THEN** the Search control is present with its label visible

### Requirement: Honest degradation and attribution

When the cascade returns no results or is unreachable, the response SHALL
report the empty provider and instruct the model to state that live search was
unavailable; source chips SHALL be attributed to the cascade provider and
SHALL NOT be labelled as Google results.

#### Scenario: Cascade dry
- **WHEN** budgets are exhausted or the search key is missing
- **THEN** the answer says search was unavailable, `groundingSources` is
  empty, and no invented URLs appear

### Requirement: Budget-bounded chat search

Chat search SHALL consume only metered free-tier providers via the edge
cascade and SHALL NOT introduce any paid or unmetered search path.

#### Scenario: Provider budget spent
- **WHEN** Tavily's monthly meter is exhausted
- **THEN** the edge skips Tavily and serves from Exa without billing either
  provider beyond its budget
