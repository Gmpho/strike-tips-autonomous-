# 🏇 Strike Tips Test Suite Record

This document lists all the automated tests implemented in the **Strike Tips** project, detailing their coverage, parameters, and the latest successful test run reports.

---

## 📂 Test Suites Overview

The test suite consists of **3 main test modules** located in the `core_agent/tests/` directory:

| Test File | Total Test Cases | Primary Coverage Areas |
|-----------|------------------|------------------------|
| **[`test_dsi_staking.py`](./test_dsi_staking.py)** | 1 | Dream Stress Index (DSI) calculations and dynamic Kelly sizing scaling checks. |
| **[`test_exotics.py`](./test_exotics.py)** | 9 | Formline parser cleaning, jockey/trainer combo rates, dynamic Bipot/PA/Jackpot starts mapping, and full card analysis tools. |
| **[`test_governor.py`](./test_governor.py)** | 5 | Bankroll governor lifecycle, Half-Kelly sizing limits, bet status settling, daily loss circuit breakers, and daily report generation. |

---

## 🔍 Detailed Test Cases & Coverage

### 1. DSI Staking Tests (`test_dsi_staking.py`)
*   **`test_dsi_stake_scaling`**:
    *   *Verification*: Sets up a persistent local ChromaDB instance with mock embedding functions. Inserts a combination of positive and negative simulated scenarios (dreams) to establish a 75% Dream Stress Index (DSI) for a specific track and race.
    *   *Expectation*: Confirms that the Bankroll Governor queries these mock dreams, computes the 75% DSI, and scales down the calculated Half-Kelly stake by exactly **0.50x** (Quarter-Kelly fallback).

### 2. Exotics & Parser Tests (`test_exotics.py`)
*   **`test_extract_form_string`**: Verifies that form strings (e.g. `21-1321`) are parsed accurately while ignoring horse numbers (e.g. `#10`) and weight parameters (e.g. `60kg`).
*   **`test_detect_jockey_trainer`**: Validates the extraction of trainer and jockey names from multiple inline formats (e.g. `/` symbols, `Trainer X, jockey Y`, or keyword lists).
*   **`test_get_jockey_trainer_multiplier`**: Ensures that trainer/jockey combinations from major racing stables return correct win probability multipliers.
*   **`test_compute_win_probability`**: Tests that win probabilities are correctly adjusted for horse weights (above/below 58kg baseline) and are safely bounded between `0.01` and `0.75`.
*   **`test_build_exotics_blueprint`**: Verifies that leg starting points are dynamically mapped from race headers.
*   **`test_pool_detection_exceeds_races`**: Ensures that declared pool starts extending beyond the total number of races are omitted gracefully.
*   **`test_analyze_full_race_card`**: Runs the end-to-end card analyzer tool against a mock race card string, checking for successful report formatting.
*   **`test_exotics_module_reimport`**: Verifies that the new `core_agent/skills/exotics/` modular extraction imports correctly inside the tool registry.
*   **`test_empty_form_empty_return`**: Confirms that empty or corrupted form lines do not crash the engine and return a safe baseline probability instead.

### 3. Bankroll Governor Tests (`test_governor.py`)
*   **`test_governor_initialization`**: Verifies starting bankroll parameters, peak limits, and default empty states.
*   **`test_calculate_max_stake`**: Validates the Half-Kelly formula, the 5% maximum stake cap, and the 5% minimum edge floor (bets with <5% edge return `0.0` stake).
*   **`test_record_and_settle_bet`**: Runs the complete lifecycle of a single win bet: recording it as `PENDING`, calculating exposure, settling as `WON` or `LOST`, and verifying ledger math.
*   **`test_daily_loss_limit_with_exposure`**: Tests the circuit breaker. Confirms that placing multiple bets at risk is blocked once total open exposure breaches the configured **20% daily loss limit**.
*   **`test_generate_daily_report`**: Verifies that the governor can compile structured daily performance reports.

---

## 🖥️ Execution Commands

To execute the automated test suite:

### Option A: Local Host Environment
Run from the root directory with `venv_linux` active:
```bash
PYTHONPATH=. venv_linux/bin/pytest core_agent/tests/ -v
```

### Option B: Docker Container (Live Environment)
Run the test suite inside your running `strike-bot` container:
```bash
docker exec strike-bot-new python3 -m pytest core_agent/tests/ -v
```

---

## 🏆 Latest Verification Run Report

**Date**: July 3, 2026  
**Status**: 🟢 **ALL 15 TESTS PASSED**

```
============================= test session starts ==============================
platform linux -- Python 3.10.20, pytest-9.0.3, pluggy-1.6.0 -- /usr/local/bin/python
cachedir: .pytest_cache
rootdir: /app
plugins: logfire-4.36.0, asyncio-1.4.0, anyio-4.13.0
asyncio: mode=strict, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 15 items

core_agent/tests/test_dsi_staking.py::test_dsi_stake_scaling PASSED      [  6%]
core_agent/tests/test_exotics.py::test_extract_form_string PASSED        [ 13%]
core_agent/tests/test_exotics.py::test_detect_jockey_trainer PASSED      [ 20%]
core_agent/tests/test_exotics.py::test_get_jockey_trainer_multiplier PASSED [ 26%]
core_agent/tests/test_exotics.py::test_compute_win_probability PASSED    [ 33%]
core_agent/tests/test_exotics.py::test_build_exotics_blueprint PASSED    [ 40%]
core_agent/tests/test_exotics.py::test_pool_detection_exceeds_races PASSED [ 46%]
core_agent/tests/test_exotics.py::test_analyze_full_race_card PASSED     [ 53%]
core_agent/tests/test_exotics.py::test_exotics_module_reimport PASSED    [ 60%]
core_agent/tests/test_exotics.py::test_empty_form_empty_return PASSED    [ 66%]
core_agent/tests/test_governor.py::test_governor_initialization PASSED   [ 73%]
core_agent/tests/test_governor.py::test_calculate_max_stake PASSED       [ 80%]
core_agent/tests/test_governor.py::test_record_and_settle_bet PASSED     [ 86%]
core_agent/tests/test_governor.py::test_daily_loss_limit_with_exposure PASSED [ 93%]
core_agent/tests/test_governor.py::test_generate_daily_report PASSED     [100%]

======================= 15 passed, 5 warnings in 11.76s ========================
```
