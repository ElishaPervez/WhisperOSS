# Plan: Translation Integration (Post-Transcription LLM)

## Phase 1: Data Model & UI
- [ ] Task: Update Config and Prompts
    - [ ] Subtask: Add `translation_enabled` and `target_language` to `src/config_manager.py`.
    - [ ] Subtask: Add `SYSTEM_PROMPT_TRANSLATOR` with `{language}` placeholder to `src/prompts.py`.
- [ ] Task: Update MainWindow GUI
    - [ ] Subtask: Write tests for the new UI elements.
    - [ ] Subtask: Add "Convert" toggle and "Target Language" QLineEdit to `src/ui_main_window.py`.
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
