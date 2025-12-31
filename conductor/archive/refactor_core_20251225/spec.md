# Specification: Refactor and Stabilize Core Architecture

## 1. Overview
The goal of this track is to transition the existing WhisperOSS codebase from a script-based, potentially monolithic structure into a modular, testable, and maintainable architecture. The primary focus is on decoupling core components (Audio Recording, API Client, UI) and introducing a comprehensive test suite to meet the project's >80% coverage requirement.

## 2. Goals
- **Decouple Components:** Separate concerns clearly between the UI (PyQt6), Business Logic (Audio processing, API communication), and Configuration.
- **Improve Testability:** Isolate dependencies to allow for easier unit testing of individual components.
- **Achieve >80% Test Coverage:** Implement a robust test suite for all refactored modules.
- **Maintain Functionality:** Ensure no regression in existing features (Voice typing, Formatting, Visualizer) during the refactor.

## 3. Scope
- **Audio Recorder:** Refactor `audio_recorder.py` to be a standalone class with clear interfaces for start/stop/data retrieval, decoupling it from the UI directly.
- **Groq Client:** Ensure `groq_client.py` handles API interactions robustly, with proper error handling and mockability.
- **Config Manager:** Standardize configuration loading/saving in `config_manager.py` to be robust and testable.
- **UI Logic:** Move business logic out of `ui_main_window.py` and `main.py` into dedicated controllers or service classes where appropriate.
- **Testing:** Create a `tests/` directory and implement unit tests for all the above.

## 4. Non-Goals
- Adding new user-facing features (this is strictly a refactor and stabilization track).
- Changing the visual design of the application.

## 5. Technical Approach
- **Dependency Injection:** Use dependency injection principles where possible to make components testable.
- **Pytest:** Use `pytest` as the testing framework.
- **Mocking:** Use `unittest.mock` to mock hardware (microphone) and network (API) calls during tests.
