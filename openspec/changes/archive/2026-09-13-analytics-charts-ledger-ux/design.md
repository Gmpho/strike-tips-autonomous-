## Context

Hand-rolled charts couldn't do diverging bars, heatmaps, or honest denominators; the ledger showed oldest-first rows with no timestamps. ApexCharts v6+/7 treeshakes to core + 7 types (~150KB chunk, lazy). react-apexcharts 2.x predates React 19, hence the 40-line native wrapper.

## Goals / Non-Goals

**Goals:** banking look, fast first paint, honest settled-only math, full-history ledger UX.

**Non-Goals:** premium Apex features (watermarked without a key); realtime chart streaming (SSE already updates store, charts re-render).

## Decisions

* Native wrapper with explicit updateOptions effect (mount-once, update-on-props).
* Heatmap cells need explicit colorScale ranges + shadeIntensity (auto-shades rendered near-uniform in testing).
* Equity "Start" anchor (non-date) mapped to day-before-first-point (a single bad x killed the whole curve).
* Telemetry JSONL mirror (250-line cap) because Redis fanout has no subscriber and Modal has no Redis; serve merges file+memory with a 30s reload lag accepted for ops data.
* Fast poll 10s: ~19.5k Function invocations/day/client vs 100k free quota — safe with headroom for 3+ concurrent clients.
