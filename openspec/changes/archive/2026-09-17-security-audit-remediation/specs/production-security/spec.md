## ADDED Requirements

### Requirement: Chroma compound filters

Multi-condition Chroma `where` clauses SHALL use `$and` syntax. Single-condition filters are unchanged.

#### Scenario: Freshness gate query
- **WHEN** checking today's insight for a horse/course/region
- **THEN** the query returns matches instead of throwing, and rebuilt insights stop wasting Groq calls
