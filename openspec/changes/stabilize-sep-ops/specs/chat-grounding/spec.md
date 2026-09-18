# chat-grounding Specification (delta)

## Purpose

End invented tracks, dates, and cards in AI chat ("Rand Stadium", wrong
days, fantasy meetings). Grounding is enforced in the router, not hoped
for in prompts.

## Requirements

### ADDED Requirements

#### Existence gate

The system SHALL refuse card-data requests that match no live meeting
instead of passing them to a model.

- **WHEN** a message asks FOR card data (race/card/odds/today + ask-verb)
  and no snapshot course matches and no data branch answered
- **THEN** the router SHALL return the real meetings list (or a
  feed-not-synced notice when the snapshot is empty) and SHALL NOT invoke
  any model for the request.

#### Pasted-card passthrough

The system SHALL NOT gate analysis of user-provided cards.

- **WHEN** a message contains runner data (decimal odds, `Form:`)
- **THEN** `_asks_for_card` SHALL be false and the message SHALL flow to
  normal analysis with the grounding prefix attached.

#### Grounding prefix

The system SHALL prepend today's real SAST date, live meetings, and a
no-invention rule to every model-bound message, and SHALL instruct the
model to name missing cards plainly.
