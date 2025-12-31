# Plan: Translation Integration (Post-Transcription LLM)

## Phase 1: Data Model & UI
- [x] Task: Update Config and Prompts
    - [x] Subtask: Add `translation_enabled` and `target_language` to `src/config_manager.py`.
    - [x] Subtask: Add `SYSTEM_PROMPT_TRANSLATOR` with `{language}` placeholder to `src/prompts.py`.      
- [x] Task: Update MainWindow GUI
    - [x] Subtask: Write tests for the new UI elements.
    - [x] Subtask: Add "Translate" toggle and "Language to translate to" QLineEdit to `src/ui_main_window.py`.
- [ ] Task: Conductor - User Manual Verification 'Data Model & UI' (Protocol in workflow.md)
## Phase 2: Translation Logic
- [ ] Task: Refactor Transcription Worker
    - [ ] Subtask: Write tests for prompt switching logic in `TranscriptionWorker`.
    - [ ] Subtask: Update `TranscriptionWorker` in `src/controller.py` to handle the new translation flow.
- [ ] Task: Update Controller State
    - [ ] Subtask: Connect UI signals for translation to the config manager.
- [ ] Task: Conductor - User Manual Verification 'Translation Logic' (Protocol in workflow.md)

## Phase 3: Final Verification
- [ ] Task: Verify Multi-language Output
    - [ ] Subtask: Test translation into different languages (e.g., Urdu, Spanish) to ensure character encoding and accuracy.
- [ ] Task: Conductor - User Manual Verification 'Final Verification' (Protocol in workflow.md)
