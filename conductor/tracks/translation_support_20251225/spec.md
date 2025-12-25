# Specification: Translation Support (English/Urdu)

## 1. Overview
This feature adds the ability to automatically translate transcribed text into a target language (initially English and Urdu). A new "Convert" toggle and a language selector will be added to the GUI. When enabled, the transcription will be processed by a Groq LLM to perform the translation before being outputted.

## 2. Goals
- **Multi-language Output:** Support translating spoken input into Urdu or English.
- **UI Integration:** Add intuitive controls ("Convert" toggle and Language dropdown) to the main window.
- **Config Persistence:** Save the translation settings (enabled/disabled, target language) in the user's configuration.
- **High Quality Translation:** Use LLM-based translation (Llama 3) for natural results.

## 3. Scope
- **Config Manager:** Add `translation_enabled` and `target_language` to `DEFAULT_CONFIG`.
- **UI:** 
    - Add `translation_toggle` (AnimatedToggle) and `language_combo` (QComboBox) to `MainWindow`.
    - Support Urdu and English in the dropdown.
- **Controller:** Update `WhisperAppController` to handle translation state changes.
- **Groq Client:** Add or update a method to perform translation specifically.
- **Transcription Worker:** Update the `run` method to include a translation step if enabled.

## 4. Technical Approach
- **Translation Prompt:** A dedicated system prompt will be used for translation to ensure accuracy and prevent chat-like responses from the LLM.
- **Urdu Support:** Ensure the UI and the Groq LLM handle Urdu (UTF-8) correctly.
- **TDD:** Write unit tests for the new configuration keys and the translation logic in the worker.
