https://www.racenet.com.au/form-guide/horse-racing
https://www.punters.com.au/form-guide/
https://betting.betfair.com/horse-racing/racecards/
https://www.racingpost.com/
https://www.timeform.com/horse-racing/racecards
https://www.racingandsports.com.au/form-guide/thoroughbred/south-africa
https://www.skysports.com/racing/racecards
https://legacy.winningform.co.za/
https://www.attheraces.com/racecards
https://www.racingtv.com/racecards
https://raceform.co.za/cards-results
https://www.betway.co.za/sport/horse-racing?eventType=today


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 🧠 MULTI-MODEL AI ARCHITECTURE — IMPLEMENTATION PLAN v2.0
    Strike Tips Racing Bot | Hardware: 16GB RAM / 256GB SSD
    Date: 2026-04-18 | Updated: core_agent/ refactor
 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

> **⚠️ Note:** Key changes - `strike-tips/` → `core_agent/`, removed Pydantic AI

═══════════════════════════════════════════════════════════════
SECTION 1 — MODEL INVENTORY & ROLE ASSIGNMENT (v2.0)
═══════════════════════════════════════════════════════════════

Current Ollama Models (ollama list — 2026-03-13):

  MODEL                         SIZE      TYPE       CAPABILITIES
  ──────────────────────────── ────────── ─────────── ────────────────────────────────
  gemini-3-flash-preview:cloud  ~0MB*     Cloud API   completion, tools, grounding
  kimi-k2-thinking:cloud        ~0MB*     Cloud API   completion, thinking, parallel
  kimi-k2.5:cloud               ~0MB*     Cloud API   completion, tools
  llama3.2:1b                   1.3 GB    Local       completion, TOOL CALLING
  deepseek-r1:1.5b              1.1 GB    Local       completion, thinking (CoT)
  embeddinggemma:300m           621 MB    Local       EMBEDDINGS ONLY (ctx: 2048)

  *cloud models use zero local RAM — API token cost applies only

RAM BUDGET (16GB total):
  System + Chrome:               ~3.5 GB
  Ollama daemon:                 ~0.3 GB
  FastAPI + uvicorn:             ~0.2 GB
  Telegram bot process:          ~0.1 GB
  ChromaDB (memory-mapped):      ~0.5 GB
  Next.js dev server:            ~0.4 GB
  ────────────────────────────── ─────────
  OVERHEAD TOTAL:                ~5.0 GB
  AVAILABLE FOR MODELS:         ~11.0 GB

  All 3 local models loaded simultaneously:
    llama3.2:1b (Q8_0):         ~1.4 GB
    deepseek-r1:1.5b (Q4_K_M):  ~1.2 GB
    embeddinggemma:300m (BF16):  ~0.7 GB
  ────────────────────────────── ─────────
  ALL LOCAL MODELS TOGETHER:    ~3.3 GB  OK — 7.7 GB headroom!

  RULE: Never load more than 2 local generation models at once.
  EmbeddingGemma can stay loaded permanently (621MB, embedding-only).


═══════════════════════════════════════════════════════════════
SECTION 2 — MODEL ROLES (GOD MODE AI ARCHITECTURE)
═══════════════════════════════════════════════════════════════

  ROLE                    MODEL                          WHEN TO USE
  ─────────────────────── ────────────────────────────── ──────────────────────────────────────────
  PRIMARY ORCHESTRATOR    gemini-3-flash-preview          All Telegram / API agent loops
    Tier 1 (free)         + gemini-2.5-flash              Tool calling, race analysis, tips gen
                          + gemini-2.0-flash-lite         Auto-rotates through chain on 429
                          + gemini-1.5-flash

  ORCHESTRATOR            groq/llama-3.3-70b-versatile    FREE Tier 5 — kicks in when ALL Gemini
  FALLBACK Tier 5 (free)  (console.groq.com — free)       quotas are exhausted. Extremely fast
                                                          (LPU chips). Full tool calling. 14,400
                                                          req/day free. Zero local RAM cost.

  PARALLEL TASKS          kimi-k2-thinking:cloud          Multi-race simultaneous scan
                                                          Consensus predictions across races
                                                          Dispatched by orchestrator as subtasks

  SCRAPING BRAIN          llama3.2:1b (local)             HTML/JSON content extraction
                                                          LLM-assisted runner data parsing
                                                          Fast + light + tool-calling capable
                                                          Also: ultimate local orchestrator
                                                          fallback (Tier 7, offline capable)

  DEEP REASONING          deepseek-r1:1.5b (local)        Value bet edge calculations (CoT)
                                                          Kelly Criterion analysis
                                                          Cloud fallback (quota exhausted)

  EMBEDDINGS              embeddinggemma:300m (local)     ChromaDB vector storage
                                                          Semantic race history lookup
                                                          query_memory tool

  CLOUD REASONING         kimi-k2.5:cloud                 Secondary cloud when both Gemini
  FALLBACK Tier 6                                          and kimi-k2-thinking hit quota

  AGENT LOOP DECISION FLOW (7-Tier Resilience Chain):
  +───────────────────────────────────────────────────────────────────+
  |  User Message (Telegram or API)                                   |
  |          |                                                        |
  |  [1] gemini-3-flash-preview  — primary orchestrator + tools       |
  |          | (429 quota)                                            |
  |  [2] gemini-2.5-flash        — Gemini fallback 2                  |
  |          | (429 quota)                                            |
  |  [3] gemini-2.0-flash-lite   — Gemini fallback 3                  |
  |          | (429 quota)                                            |
  |  [4] gemini-1.5-flash        — Gemini fallback 4                  |
  |          | (all Gemini exhausted)                                 |
  |  [5] groq/llama-3.3-70b      — FREE non-Gemini cloud (FAST LPU)   |
  |          | (Groq quota or down)                                   |
  |  [6] kimi-k2.5:cloud         — Ollama cloud reasoning fallback    |
  |          | (all cloud down)                                       |
  |  [7] deepseek-r1:1.5b local  — grounded CoT, fully offline        |
  |          | (deepseek slow/empty)                                  |
  |  [8] llama3.2:1b local       — ultimate fast offline response     |
  +───────────────────────────────────────────────────────────────────+

  SCRAPING PIPELINE (separate from agent loop):
  +──────────────────────────────────────────────────────────────+
  |  Raw HTML / JSON from TAB4Racing / DuckDuckGo / PDF          |
  |          |                                                   |
  |  [1] llama3.2:1b — extract structured runner JSON           |
  |          |                                                   |
  |  [2] embeddinggemma:300m — embed -> ChromaDB store          |
  |          |                                                   |
  |  [3] deepseek-r1:1.5b — analyze value edge from data        |
  +──────────────────────────────────────────────────────────────+


═══════════════════════════════════════════════════════════════
SECTION 3 — FILES TO CREATE / MODIFY
═══════════════════════════════════════════════════════════════

[NEW] core_agent/config/model_config.py

[MODIFY] .env — add these model role keys (already present in v2.0):

[MODIFY] core_agent/agents/ai_providers.py

[MODIFY] core_agent/core/strike_tips.py — add LLM extraction using llama3.2:1b:

[MODIFY] core_agent/skills/memory/chroma_memory.py
  [DONE] Replaced hardcoded "embeddinggemma:300m" with ModelConfig.EMBEDDER via _make_embedding_fn()
  [DONE] Added cloud/local ChromaDB detection (CHROMA_API_KEY/CHROMA_HOST)
  [DONE] Added embedding fallback chain: Ollama → Gemini → ChromaDB default


═══════════════════════════════════════════════════════════════
SECTION 4 — BUSINESS LOGIC ADVICE (L7 Senior Review)
═══════════════════════════════════════════════════════════════

STRENGTHS — What is working well:
  • Half-Kelly (0.5) conservative staking — correct for SA racing variance
  • 5% max bet + 20% daily loss limit at BankrollGovernor level
  • Grounded truth: PDF -> memory -> web search before answering
  • ChromaDB memory prevents repeat API calls for same data
  • 3-tier fallback (Gemini -> Kimi Cloud -> Local) — solid resilience
  • Typing indicator + message chunking in Telegram — production UX

GAPS & RECOMMENDATIONS:

  1. MULTI-SOURCE ODDS CONSENSUS (HIGH VALUE)
     Problem: Single-source odds from TAB4Racing. Wrong odds = wrong edge.
     Fix: Cross-reference TAB vs Betway SA decimal odds.
          Average both; flag >5% discrepancy as "Odds Alert" in Telegram.
     Location: strike_tips.py -> run_daily_scan()
     Impact: Removes false-positive value bets.

  2. FORM WEIGHTING TOO STATIC (MEDIUM VALUE)
     Problem: Raw "1-2-1" string passed to AI — interpreted inconsistently.
     Fix: Pre-process in form_analyzer.py:
          Last 3 runs weighted 60/30/10%
          +10% bonus for distance-match win
          +5% bonus for track-specific placing
     Impact: 10-15% improvement in probability estimation accuracy.

  3. JOCKEY + TRAINER STRIKE RATES MISSING (HIGH VALUE)
     Problem: Names passed as strings — no SA-specific win rate data.
     Fix: data/jockey_stats.json + data/trainer_stats.json
          Weekly scrape from winningform.co.za or raceform.co.za
          Inject win-rate as structured data in the race prompt
     Impact: 15-20% edge calculation improvement — biggest single win.

  4. RACE RESULT AUTO-SETTLEMENT MISSING (STRATEGIC)
     Problem: Bets placed but results verified manually. No closed-loop PnL.
     Fix: scheduler.py job at 18:00 SAST daily:
          -> Query TAB V4 API for results
          -> Auto-settle open bets in bankroll.json
          -> Store race outcomes in ChromaDB memory
          -> Send Telegram daily P&L summary
     Impact: Full automation loop — the biggest missing piece currently.

  5. BANKROLL.JSON CORRUPTION RISK (CRITICAL / 5 MINUTES TO FIX)
     Problem: If bankroll.json corrupt, silently resets to R1000.
     Fix: Write backup on every save. Load backup if primary fails.

  6. RACE SURFACE / CONDITION WEIGHTING (MEDIUM)
     Problem: "condition: Good" hardcoded. Greyville Polytrack != Turffontein Turf.
     Fix: Map surface from config/settings.py TRACKS dict into the AI prompt.
          Add per-horse surface preference derived from form history.


═══════════════════════════════════════════════════════════════
SECTION 5 — SWAPPABILITY DESIGN
═══════════════════════════════════════════════════════════════

  Any model swaps via .env — no source code changes ever needed:

  Try mistral for scraping:      MODEL_SCRAPER=mistral:7b
  Try qwen for reasoning:        MODEL_REASONER=qwen2.5:3b
  Add new pulled model:          MODEL_ORCHESTRATOR=phi4-mini
  Add Groq provider:             GROQ_API_KEY=... -> add _call_groq() method

  All agent loops, scraper, and memory pick up the new model on restart.


═══════════════════════════════════════════════════════════════
SECTION 6 — PHASED ROLLOUT
═══════════════════════════════════════════════════════════════

  PHASE 1 — Config Layer  (Zero Risk — Do This First)
  [ ] Create config/model_config.py
  [ ] Add model role keys to .env
  [ ] Replace 4 hardcoded model strings in ai_providers.py with ModelConfig
  [ ] Add bankroll.json backup-on-write (5 lines of code)
  [ ] Set OLLAMA_KEEP_ALIVE=5m in .env
  TEST: restart api.py + telegram bot -> verify zero behavior change

  PHASE 2 — Scraper Llama Brain
  [ ] Add _llm_extract_runners() to scraper.py
  [ ] Guard: only invoke when standard parse returns < 3 runners
  TEST: run scraper.py -> verify runner extraction quality

  PHASE 3 — Kimi K2 Parallel Dispatch
  [ ] Add _call_kimi_parallel() to AIProvider
  [ ] Wire into run_daily_scan() for parallel multi-race analysis
  TEST: POST /api/scan -> verify parallel responses returning

  PHASE 4 — Business Logic Improvements (Highest ROI)
  [ ] Pre-process form strings in form_analyzer.py (recency weighting)
  [ ] Add jockey_stats.json + trainer_stats.json + weekly scrape script
  [ ] Inject stats into race prompt builder in ai_providers.py
  [ ] Add race result auto-settlement job in scheduler.py at 18:00

  PHASE 5 — Multi-Source Odds Consensus
  [ ] Add Betway SA as secondary scrape via llama extractor
  [ ] Average decimal odds TAB vs Betway before edge calculation
  [ ] Send Telegram "odds alert" when discrepancy > 5%


═══════════════════════════════════════════════════════════════
SECTION 7 — QUICK WINS (DO TODAY — UNDER 1 HOUR EACH)
═══════════════════════════════════════════════════════════════

  1. Add OLLAMA_KEEP_ALIVE=5m to .env -> saves ~2GB RAM between model runs
  2. Create config/model_config.py -> immediate swappability, zero risk
  3. Add bankroll.json backup-on-write -> prevents catastrophic data loss
  4. Confirm stop tokens in ALL local calls: ["<think>","</think>","\n\n\n\n"]
     Already in _call_ollama() — enforce this in any new local calls too
  5. Add performance_tracker.track_request() to _call_kimi_parallel()
     so parallel Kimi calls show up in the metrics dashboard


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
END — Strike Tips Multi-Model Architecture Plan v1.0  (2026-03-13)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━




  🔍 Ground Truth & Research Summary
   1. DeepSeek-R1:1.5B (Local): Small footprint (~1.1GB), but needs num_ctx manually increased to
      handle racing form data. Excellent for reasoning.
   2. Llama-3.2:1B (Local): Ultra-light (~1.3GB). This is our "speed demon" for scraping and     
      categorization.
   3. Kimi-K2.5:cloud (Cloud): The heavy hitter. Offloads 1-Trillion parameter logic to the      
      cloud, giving us a massive 256K context window for global racing analysis without touching 
      your local RAM.
   4. Gemini-3-Flash (Cloud): Our reliable fallback and primary orchestrator.



racingsa.co.za
- sportingpost.co.za
- tabonline.co.za
- news24.com
- timeslive.co.za
- espn.com (or espn.co.uk)
- sport24.co.za
- sabra.co.za
- skyracing.com
- sportinglife.com (horse racing)
- racingpost.com
- at-the-racks.co.za
- goldcircle.co.za
- bloodhorse.com
- thoroughbredracing.com
- equinews.com
