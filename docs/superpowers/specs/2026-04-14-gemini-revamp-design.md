# WhisperOSS Gemini Revamp Design

**Date:** 2026-04-14

## Goal

Replace the Antigravity proxy workflow with official Google Gemini API usage, keep Groq for transcription, support streamed Gemini answers with Google Search grounding, and simplify the app so only Groq + Gemini remain as runtime providers.

## Scope

- Remove proxy-specific config, client code, UI, tests, and README/docs references from the app.
- Add official Gemini-backed search and image-question flows.
- Keep Groq transcription and optional Groq formatting/translation intact unless directly affected by the provider cleanup.
- Expose a user-editable Gemini model setting, defaulting to `models/gemma-4-31b-it`.
- Reduce coupling introduced by the proxy workflow by narrowing controller responsibilities where practical in the touched areas.

## Architecture

### Runtime providers

- `GroqClient` remains responsible for speech transcription and existing formatter calls.
- A new `GeminiClient` becomes responsible for:
  - listing Gemini models
  - running grounded text answers
  - running grounded image-assisted answers
  - streaming partial answer text to the UI

### Search pipeline

- `SearchWorker` will no longer depend on `ProxySearchClient`.
- Search input stays simple:
  - transcribe speech with Groq when needed
  - combine query text with selected text context when present
  - send the resulting prompt to Gemini
- Streaming remains worker-driven:
  - worker emits progress updates
  - worker emits cumulative streamed answer text
  - controller forwards those chunks to the floating visualizer

### UI/config

- Settings only expose:
  - Groq API key
  - Gemini API key
  - Gemini model
  - existing audio/appearance/output settings that still apply
- Remove proxy toggles, proxy URL/key/model fields, proxy formatter model field, and proxy help text.
- Keep the main window structure, but reduce provider complexity to a direct two-key configuration.

## Data model changes

### Remove config keys

- `use_antigravity_proxy_search`
- `antigravity_proxy_url`
- `antigravity_api_key`
- `antigravity_search_model`
- `antigravity_search_fallback_model`
- `antigravity_thinking_level`
- `proxy_formatter_model`

### Add config keys

- `gemini_api_key`
- `gemini_model`

### Retained formatting behavior

- `format_provider` remains only if Groq/Gemini formatting selection is intentionally preserved.
- If formatting stays Groq-only, `format_provider` should be removed too.

## UX behavior

- Quick answer mode uses Gemini with Google Search grounding by default.
- Image-question mode uses Gemini with the selected image region and the same grounding-enabled request path.
- The floating visualizer continues to show:
  - processing status
  - streamed answer growth
  - final answer card

## Error handling

- Missing Gemini key should surface a direct configuration error.
- Gemini request failures should emit explicit worker errors and cancel the visualizer cleanly.
- Model-list fetch failures should not crash initialization; the editable model field still allows manual entry.

## Testing

- Add Gemini client unit tests for model listing, grounded requests, and streaming parsing.
- Update worker/controller tests to assert Gemini-backed search behavior instead of proxy behavior.
- Remove proxy-specific tests.
- Keep focused UI tests for the new Gemini settings controls.

## Risks

- Streaming response handling is the highest-risk behavior change.
- The controller currently touches UI internals; this revamp should reduce new coupling, not expand it.
- There are existing uncommitted edits in `src/controller.py`, `src/prompts.py`, and `src/services/groq_service.py`; changes in those files must preserve unrelated user work.
