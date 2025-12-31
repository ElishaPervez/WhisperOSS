# Specification: Translation Integration (Post-Transcription LLM)

## 1. Overview
This feature introduces a more reliable translation mechanism by leveraging a large language model (GPT OSS 120B or similar via Groq) to process transcribed text. It adds a "Convert" toggle and a target language input field to the GUI. When active, the application uses a specialized system prompt that instructs the LLM to both format and translate the text.

## 2. Goals
- **High-Fidelity Translation:** Outperform Whisper's built-in translation by using LLM-based post-processing.
- **Unified Prompting:** Create a specialized system prompt for simultaneous formatting and translation.
- **Intuitive GUI:** Add a "Translate" toggle and a "Language to translate to" input field.
- **Config Persistence:** Save translation state and target language preferences.

## 3. Scope
- **Config Manager:** Add `translation_enabled` and `target_language` to defaults.
- **Prompts:** Add `SYSTEM_PROMPT_TRANSLATOR` to `src/prompts.py`.
- **UI:** 
    - Add "Translate" toggle (`AnimatedToggle`) to `MainWindow`.
    - Add "Language to translate to" input field (`QLineEdit`) to `MainWindow`.
- **Controller/Worker:**
    - Update `TranscriptionWorker` to switch system prompts based on translation toggle.
    - Update `WhisperAppController` to synchronize UI state with configuration.

## 4. Technical Approach
- **Dynamic Prompting:** The `TranscriptionWorker` will select between `SYSTEM_PROMPT_FORMATTER` and `SYSTEM_PROMPT_TRANSLATOR`.
- **Placeholder Handling:** The `SYSTEM_PROMPT_TRANSLATOR` will use a placeholder (e.g., `{language}`) that the worker populates before sending the request.
- **UTF-8 Support:** Ensure UI and clipboard handling support non-Latin character sets (e.g., Urdu, Chinese, Arabic).
