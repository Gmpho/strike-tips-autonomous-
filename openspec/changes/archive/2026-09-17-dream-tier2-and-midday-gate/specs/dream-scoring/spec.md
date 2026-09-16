## ADDED Requirements

### Requirement: Automatic tier selection

`generate_dream` with `allow_llm=None` (default) SHALL select Tier-2 (Groq sim) when an open ticket exists for the dream's track+race, else Tier-1 (deterministic screen). Explicit True/False SHALL override.

#### Scenario: Bet race earns a sim
- **WHEN** a dream targets a race holding a PENDING ticket
- **THEN** a Groq sim runs with enriched inputs

#### Scenario: Quiet race screened free
- **WHEN** a dream targets a race with no open tickets
- **THEN** no Groq call is made (tested: Groq entry raises if touched)

### Requirement: Enriched custom dreams

User-invoked custom dreams SHALL include Betfair brief lines and enriched shift math like background dreams.

#### Scenario: /dream command
- **WHEN** a user dreams a specific track/race with a scenario
- **THEN** the prompt carries that race's Betfair briefs
