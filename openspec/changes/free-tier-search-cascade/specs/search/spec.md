# Capability: free-tier-search

## Purpose

Real-time web research for edge chat and the agent without paid search.
Tavily (1000 free credits/mo) and Exa (~1400/mo) cascade ahead of the free
floor, metered so loops can never eat the month.

## ADDED Requirements

### Requirement: Provider cascade order

Web search SHALL try Tavily first, then Exa, then the free floor (DDGS on
backend, Brave-keyed path on edge), returning the first non-empty result
set with its provider named.

#### Scenario: Tavily answers
- **WHEN** Tavily returns results
- **THEN** the response carries `provider: "tavily"` and no other provider
  is called

### Requirement: Spend meters

Each metered call SHALL increment a monthly counter (KV on edge, JSON
sidecar backend); exhausted providers SHALL be skipped without calling.

#### Scenario: Budget exhausted
- **WHEN** Tavily's 1000 monthly calls are used
- **THEN** Tavily is skipped and Exa answers instead

### Requirement: Loop protection

Identical backend queries within 6h SHALL return cached results with zero
provider calls; combined paid calls SHALL NOT exceed 40/day.

#### Scenario: Monitor re-asks
- **WHEN** the same query repeats within 6h
- **THEN** the second call hits cache and spends nothing

### Requirement: Honest degradation

When no provider can answer, the response SHALL say so with the provider
field set and an empty result list — never fabricated content.

#### Scenario: All providers dry
- **WHEN** budgets are spent and DDGS finds nothing
- **THEN** the result names the empty provider with zero items, not guesses
