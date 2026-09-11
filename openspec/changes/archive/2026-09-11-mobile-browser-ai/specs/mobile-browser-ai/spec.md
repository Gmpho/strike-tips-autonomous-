## Purpose

On-device browser AI that works offline on phones after a single Wi-Fi download, without porting external code.

## ADDED Requirements

### Requirement: Summarize on resident Qwen

The system SHALL offer a Summarize toggle that re-prompts the already-resident Qwen with the pasted text and a bullet-summary brief, without RAG or history, via WebLLM or cloud models.

#### Scenario: Summarize pasted report
- **WHEN** user pastes an article and enables Summarize
- **THEN** the model returns 3-6 bullets + one-line bottom line from that text alone

### Requirement: Sentiment badges

News cards SHALL show on-device POSITIVE/NEGATIVE badges (weak <0.6 → NEUTRAL) only after lazy enable; failures are silent.

#### Scenario: Enable and score
- **WHEN** user enables sentiment and news is present
- **THEN** badges appear per card with honest on-device attribution

### Requirement: TTS voices

Verdicts SHALL have a speaker button that speaks on-device via Supertonic with a cycleable 3-voice picker.

#### Scenario: Voice switch
- **WHEN** user taps the voice pill
- **THEN** the next utterance uses the next voice

### Requirement: Translation toggles

Verdicts SHALL have a translate button for AF/ZU/ST, each on-demand with its own model (Afrikaans Opus-MT, Zulu m2m100, Sesotho NLLB with Flores codes); failures are silent.

#### Scenario: Translate to Afrikaans
- **WHEN** user picks Afrikaans and translates a tip
- **THEN** the Afrikaans text appears beneath the verdict

### Requirement: Form image reading

An image attach SHALL read printed text via TrOCR on-device and append the extracted lines to the chat input.

#### Scenario: Attach form snippet
- **WHEN** user attaches a racecard image
- **THEN** recognized lines appear as `[Form image]` in the input

### Requirement: Offline pack

Settings SHALL offer a bulk Wi-Fi download of all on-device models with progress and per-model Ready/Not downloaded status, terminating workers after download to free VRAM.

#### Scenario: Bulk download on Wi-Fi
- **WHEN** user taps Download all on Wi-Fi
- **THEN** each model downloads sequentially with combined progress and stays cached for offline use
