# 🏇 Strike Tips Racing Bot — L7 Principal Engineer Review
**Author**: Antigravity (L7 Principal Coding Assistant)  
**Date**: June 27, 2026  
**Target Repository**: `Kimi_Agent_Strike Tips Racing Bot`  
**System Version**: V2.0 (April 2026 Refactor)

---

## 1. Executive Summary

The **Strike Tips Racing Bot** is a full-stack, autonomous betting intelligence system specifically designed for South African horse racing. It leverages a modern, event-driven loop and a tiered local/cloud LLM routing architecture to find "probability edges" (where estimated win probability exceeds the market implied odds by $\ge 5\%$) and executes trades controlled by a disciplined **Bankroll Governor**.

From an L7 engineering standpoint, the codebase exhibits strong architectural design choices—such as a decoupled **MessageBus** pattern, semantic local specialist model routing (mimicking Google AI Edge Gallery patterns), and a strict mathematical governor. However, there are significant concurrency, resilience, and software-quality vulnerabilities that present real-world operational risks to the capital under management.

---

## 2. Architecture & Design Assessment

### A. The MessageBus & AgentLoop TurnState Machine
The V2.0 refactor successfully replaces a synchronous Orchestrator/Pipeline with an asynchronous, event-driven architecture (`core_agent/bus` and `core_agent/agent`):
- **MessageBus**: Implemented using `asyncio.Queue` for inbound and outbound messages, decouples ingest channels (REST, WebSockets, Telegram) from the core intelligence loop.
- **AgentLoop**: Implements a clean State Machine following the `TurnState` lifecycle:
  `RESTORE` $\rightarrow$ `COMPACT` $\rightarrow$ `COMMAND` $\rightarrow$ `BUILD` $\rightarrow$ `RUN` $\rightarrow$ `SAVE` $\rightarrow$ `RESPOND` $\rightarrow$ `DONE`.
- **ContextBuilder**: Pulls form insights dynamically from ChromaDB and fuses them into user prompts, allowing prompt optimization prior to execution.

**Critique**: The `TurnState` transitions are hardcoded in a `while` loop within `AgentLoop.process`. While functional, it is prone to lockups or silent state drops if an unhandled exception occurs inside a state execution block. Transitioning to a structured async state machine with strict error-handling boundaries per state is recommended.

### B. TaskRouter & Google AI Edge Specialist Mapping
The routing layer (`core_agent/agent/providers/task_router.py`) is one of the most mature sections of the system:
1. **Phase 0 (Zero-Compute Reads)**: Intercepts queries (e.g., "market movers", "results", "odds") and serves them directly from local JSON snapshots stored by `odds-monitor`. This saves substantial API cost and minimizes latency (~0ms response).
2. **Semantic Specialist Routing**: Uses keyword and intent regexes to select domain-specific models:
   - `racing_llama`: Router and web search summarizer.
   - `racing_qwen`: Fast reads, account info, and basic queries.
   - `func_gemma`: Transactional and write ops (recording/settling bets).
   - `lfm_racing`: Deep, multi-step race evaluations.
   - `ds_racing`: Structured reasoning on probability edges.
3. **Cloud Fallback Chain**: Concurrently triggers cloud models (Groq $\rightarrow$ Gemini) with a $5.0$-second timeout to guarantee high availability.

**Critique**: The concurrency lookup using `asyncio.wait` with `return_when=asyncio.FIRST_COMPLETED` is highly effective. However, the `_detect_specialist` regex keyword matching is brittle. For example, any query containing the word `"wager"` maps to `record_selection` even if the user was just asking a question about a historical wager. A classification model or a structured router would improve routing precision.

---

## 3. Concurrency & Persistence Analysis

The system manages bankroll state and bet history via flat JSON files (`bankroll_state.json` and `bet_history.json`).

### A. Process-Safe File Locking
In `core_agent/skills/bankroll_manager/governor.py`, the `_atomic_transaction` context manager uses `fcntl.flock(lock_fd, fcntl.LOCK_EX)` on a lockfile (`bankroll.lock`).
- This guarantees process-safe and container-safe serial access to the JSON store across the FastAPI backend (`strike-bot`) and the background monitoring agent (`odds-monitor`).
- It correctly forces a state reload (`_load_state`) immediately *after* acquiring the lock, ensuring that concurrent transactions evaluate the latest bankroll balances.

---

## 4. Critical Bugs & Engineering Risks (Code-Level)

### 🔴 P0 Bug: Missing Await in ResultTracker main entry point
In [result_tracker.py](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/core_agent/skills/result_tracker.py#L90), the main orchestration method fails to `await` the search call:
```python
# L90 inside check_and_settle_open_bets:
result_text = self._search_result(bet.track, bet.race_number)
```
- **Consequence**: `self._search_result` is an `async def`. Calling it without `await` returns a coroutine object.
- The next line evaluates `if not result_text:`, which evaluates to `False` because the coroutine object is truthy.
- `_extract_winner(result_text, ...)` then attempts to call `.lower()` on `result_text` (the coroutine object), causing an **immediate crash (`AttributeError: 'coroutine' object has no attribute 'lower'`)**.
- *Mitigation in Production*: In [scheduler.py](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/core_agent/core/scheduler.py#L227), the scheduler bypasses this method and calls `await tracker._search_result(...)` inline. However, any call to the official skill entry point `check_and_settle_open_bets()` will fail catastrophically.

### 🔴 P0 Design Flaw: Non-Atomic File Updates
In `BankrollGovernor._save_state`, files are written directly using `open(..., "w")`:
```python
with open(self._state_file, "w") as f:
    json.dump(..., f)
```
- **Consequence**: If the container process is terminated (e.g., Docker OOM, SIGKILL, or hardware reboot) mid-write, the bankroll state file becomes empty or malformed. Since the system depends on `bankroll_state.json` to initialize, this results in **permanent state corruption and capital loss**.
- **L7 Recommendation**: Implement atomic writes using the write-to-temp-then-rename pattern:
  ```python
  import tempfile
  temp_fd, temp_path = tempfile.mkstemp(dir=self.data_dir)
  with os.fdopen(temp_fd, 'w') as tmp:
      json.dump(state_dict, tmp)
  os.replace(temp_path, self._state_file)
  ```

### 🟡 P1 Financial Risk: Unsettled Exposure Ignored by Governor
The Daily Loss Limit is defined as $20\%$ of the bankroll:
```python
daily_loss = -today_stats.profit_loss
if daily_loss >= self.current_bankroll * 0.20:
    return False, "Daily loss limit reached"
```
- **Consequence**: `today_stats.profit_loss` only evaluates settled bets (`WON` or `LOST`). It ignores `PENDING` bets.
- If the system concurrent-scans and triggers 10 value bets of $5\%$ bankroll each, the total exposure is **$50\%$ of the bankroll**. If all lose, the actual loss will be $50\%$, completely bypassing the $20\%$ daily safety limit.
- **L7 Recommendation**: The governor must evaluate **unsettled exposure** when checking limits. If `daily_loss + open_exposure >= limit`, no new positions should be recorded.

### 🟡 P2 Fragility: Stealth Scraper Fallback
In [search_service.py](file:///home/giftmpho/Kimi_Agent_Strike%20Tips%20Racing%20Bot/core_agent/skills/search_service.py#L40), the fallback for South African racing sites uses a basic `httpx` GET request:
```python
r = await client.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
```
- **Consequence**: SA racing domains (e.g., `tab4racing.com`, `topbets.co.za`) employ strict anti-bot measures (Cloudflare, PerimeterX). A simple HTTP client request without browser finger-printing, JS challenge solving, or cookies will yield a `403 Forbidden` response, making the SA-specific scraper fallbacks completely ineffective.

---

## 5. Autonomy Level & Gaps

According to the `AUTONOMY_PLAN.md` and codebase verification:
- **Current Autonomy**: **~70%**. The scheduler successfully runs from the FastAPI startup lifespan block, initializing `AdaptiveOddsMonitor`, `heartbeat` dream grounding loops, and the result check cycles.
- **Key Remaining Gaps**:
  1. **Continuous Scans**: The continuous scan job is stubbed out. It needs implementation to detect mid-day racecard changes/additional races.
  2. **Learning Engine Recalibrations**: The system records settled bets to `learning_stats.json` but doesn't run the daily analyzer updates (`update_learning_job` is `pass`).
  3. **End of Day Reports**: The Telegram summary report is stubbed.
