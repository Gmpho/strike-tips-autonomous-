"""Strike Tips predictor league — scoring, rollups and settlement helpers.

Pure logic lives in scoring.py / rollups.py (no I/O, fully unit-tested).
regions.py resolves a track name to a region code (mirrors the HUD's
src/lib/regions.ts — keep the two in sync when adding tracks).
"""