# Plan: Refactor and Stabilize Core Architecture

## Phase 1: Test Infrastructure & Configuration
- [x] Task: Set up test environment
    - [x] Subtask: Install `pytest`, `pytest-cov`, `pytest-qt` (if needed for UI tests).
    - [x] Subtask: Create `conftest.py` with initial fixtures (e.g., mock config).
- [x] Task: Refactor Config Manager
    - [x] Subtask: Write tests for `ConfigManager` (load, save, default values).
    - [x] Subtask: Refactor `src/config_manager.py` to ensure it passes tests and handles missing/corrupt files gracefully.
- [x] Task: Conductor - User Manual Verification 'Test Infrastructure & Configuration' (Protocol in workflow.md) [checkpoint: b1ad169]

## Phase 2: Core Logic Refactoring (Non-UI)
- [x] Task: Refactor Groq Client 9c6070e
    - [x] Subtask: Write tests for `GroqClient` (mocking the actual API calls).
    - [x] Subtask: Refactor `src/groq_client.py` to improve error handling and interface clarity.
- [x] Task: Refactor Audio Recorder 29997eb
    - [x] Subtask: Write tests for `AudioRecorder` (mocking PyAudio).
    - [x] Subtask: Refactor `src/audio_recorder.py` to ensure it emits signals or callbacks instead of directly manipulating UI, making it testable.
- [x] Task: Conductor - User Manual Verification 'Core Logic Refactoring (Non-UI)' (Protocol in workflow.md) [checkpoint: db8bf9f]

## Phase 3: UI Integration & Main Entry Point
- [x] Task: Refactor Main Window Logic b02edd5
    - [x] Subtask: Write tests for key UI interactions (using `pytest-qt` or by separating logic into a Controller class).
    - [x] Subtask: Update `src/ui_main_window.py` to use the refactored `ConfigManager`, `GroqClient`, and `AudioRecorder`.
- [x] Task: Clean up Main Entry Point 05dede7
    - [x] Subtask: Refactor `src/main.py` to simply bootstrap the application, ensuring clean startup/shutdown.
- [x] Task: Conductor - User Manual Verification 'UI Integration & Main Entry Point' (Protocol in workflow.md) [checkpoint: 947fe51]
