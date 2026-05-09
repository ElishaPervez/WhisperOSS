# Gemini Revamp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the proxy workflow, add official Gemini search/image streaming support, and simplify WhisperOSS to Groq + Gemini only.

**Architecture:** Keep Groq for transcription and add a focused Gemini client for grounded answer generation and model listing. Route quick-answer and image-question flows through Gemini, simplify settings/config to match the new provider model, and remove proxy-specific code, tests, and docs.

**Tech Stack:** Python, PyQt6, Groq SDK, Google Gemini API, pytest, pytest-qt

---

### Task 1: Add Gemini client tests

**Files:**
- Create: `tests/test_gemini_client.py`
- Modify: `requirements.txt`

- [ ] Write failing tests for model listing, non-streamed grounded answers, and streamed text aggregation.
- [ ] Run `pytest tests/test_gemini_client.py -v` and verify failures are caused by missing Gemini client behavior.
- [ ] Implement the minimal Gemini client and dependency updates to satisfy the tests.
- [ ] Run `pytest tests/test_gemini_client.py -v` and verify they pass.

### Task 2: Replace search worker/provider plumbing

**Files:**
- Modify: `src/services/groq_service.py`
- Modify: `tests/test_integration.py`

- [ ] Write failing worker tests for Gemini-backed text search, image search, and stream emission.
- [ ] Run the targeted worker tests and verify red.
- [ ] Implement the minimal worker changes to remove proxy assumptions and call the Gemini client.
- [ ] Re-run the targeted worker tests and verify green.

### Task 3: Replace controller wiring

**Files:**
- Modify: `src/controller.py`
- Modify: `tests/test_controller.py`

- [ ] Write failing controller tests for Gemini initialization, config updates, model refresh, and quick-answer wiring.
- [ ] Run the targeted controller tests and verify red.
- [ ] Implement the minimal controller changes to remove proxy client usage and wire Gemini instead.
- [ ] Re-run the targeted controller tests and verify green.

### Task 4: Simplify config and main window

**Files:**
- Modify: `src/config_manager.py`
- Modify: `src/ui_main_window.py`
- Modify: `tests/test_ui_main_window.py`

- [ ] Write failing UI/config tests for Gemini API key persistence, editable Gemini model selection, and absence of proxy settings.
- [ ] Run the targeted UI/config tests and verify red.
- [ ] Implement the minimal config and main-window changes to expose Gemini settings and remove proxy controls.
- [ ] Re-run the targeted UI/config tests and verify green.

### Task 5: Remove proxy residue and update docs

**Files:**
- Delete or stop referencing: `src/proxy_search_client.py`
- Modify: `README.md`
- Modify: `src/prompts.py`
- Modify: `tests/test_proxy_search_client.py`
- Modify or remove: proxy-specific probe/integration tests that no longer apply

- [ ] Write or update failing tests/doc expectations for the new Gemini-only behavior where practical.
- [ ] Remove dead proxy references from runtime code and tests.
- [ ] Update README usage/config documentation to describe Groq + Gemini only.
- [ ] Re-run the relevant focused test set and verify green.

### Task 6: Final verification

**Files:**
- Modify as needed based on verification results

- [ ] Run a focused regression suite covering Gemini client, workers, controller, UI, and remaining stable tests.
- [ ] Run any additional failing tests uncovered during the refactor and fix them.
- [ ] Summarize remaining risks if any verification gaps remain.
