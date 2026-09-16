## 1. Correlation (A1)

- [x] 1.1 `correlation.py` (new_id/bind/get/tag) + unit test
- [x] 1.2 Bound at scan/settle/chat entries; tagged settle logs; `ref` token on value-bet + result notifications

## 2. JSON logging (A2)

- [x] 2.1 `logging_setup.py` (Modal auto-detect, `LOG_FORMAT` override); wired into `modal_app` + `api_pkg`

## 3. Levels (A3)

- [x] 3.1 Demoted routine fallbacks (Betway/Betfair retries, DSI fallback, empty search, racing-odds timeouts, non-429 Groq); 429s + money-path stay warnings

## 4. Chat rendering

- [x] 4.1 Assistant messages render markdown (ReactMarkdown + GFM, theme-mapped); user bubbles plain

## 5. Ship

- [x] 5.1 Full suite green; Modal + Pages deployed; docs + README updated
