# Plan: Translation Support (English/Urdu)

## Phase 1: Data Model & UI Components
- [x] Task: Update Configuration and Constants fa9fdfd
    - [x] Subtask: Add `translation_enabled` and `target_language` to `src/config_manager.py`.
    - [x] Subtask: Add `SYSTEM_PROMPT_TRANSLATOR` to `src/prompts.py`.
- [x] Task: Add Translation Controls to UI 59511a5
    - [x] Subtask: Write tests for `MainWindow` to verify the new toggle and dropdown behavior.
    - [x] Subtask: Implement the "Convert" toggle and Language selector in `src/ui_main_window.py`.
- [ ] Task: Conductor - User Manual Verification 'Data Model & UI Components' (Protocol in workflow.md)

## Phase 2: Logic Integration
- [ ] Task: Update Groq Client for Translation
    - [ ] Subtask: Write tests for `translate_text` method in `GroqClient`.
    - [ ] Subtask: Implement `translate_text` in `src/groq_client.py`.
- [ ] Task: Update Transcription Worker
    - [ ] Subtask: Write tests for `TranscriptionWorker` to verify it calls translation when enabled.
    - [ ] Subtask: Update `TranscriptionWorker` in `src/controller.py` to handle the translation flow.
- [ ] Task: Update Controller
    - [ ] Subtask: Connect UI signals for translation to the config manager.
- [ ] Task: Conductor - User Manual Verification 'Logic Integration' (Protocol in workflow.md)

## Phase 3: Final Verification
- [ ] Task: Verify End-to-End Flow
    - [ ] Subtask: Ensure Urdu characters are correctly pasted into target applications.
- [ ] Task: Conductor - User Manual Verification 'Final Verification' (Protocol in workflow.md)
