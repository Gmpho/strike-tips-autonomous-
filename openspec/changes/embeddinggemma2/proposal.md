# Proposal: EmbeddingGemma 2 migration (text-first)

Released 2026-10-06 (day-one adoption). Text-only 270m (378MB) replaces
300m v1: same multilingual quality (61.36 vs 61.15), 8K context (4x),
MRL truncation, ~191MB RAM quantized. Vision (+170M) and audio (+300M)
are phase two (racecard PDFs/silks, podcast search).

## Status / blocker

- Code: READY (auto-detect, versioned `_v2` collections, FTS5 rewired,
  `db/reembed.py` dry-run-first migrator, tests).
- Blocker (Oct-2026, verified on container 0.40.0 AND fresh host install):
  `ollama pull embeddinggemma-2:{270m,740m}` fails with
  "requires MLX support, but the MLX runtime is not available" on Linux.
  Upstream packaging bug — wait for fixed Linux build, then:
  pull → auto-detect → reembed --live → verify → cutover.
- Fallback if Ollama never ships Linux: sentence-transformers + HF weights
  (torch in backend image; slower CPU inference — background writes OK,
  live chat grounding painful).
