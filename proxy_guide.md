# Antigravity Proxy Integration Guide (General)

This guide is for integrating the Antigravity local proxy into any project, not just WhisperOSS.

It is based on proxy behavior in current source/docs (4.1.23 era) and focuses on:
- protocol compatibility
- streaming
- reasoning/thinking handling
- robust fallbacks

## 1) Core Endpoints

Proxy root:
- `http://127.0.0.1:8045`

Common endpoints:
- `POST /v1/chat/completions`
- `POST /v1/completions`
- `POST /v1/responses`
- `POST /v1/messages`
- `GET /v1/models`
- `GET /v1beta/models` (Gemini-style listing)

## 2) SDK Base URL Mapping

- OpenAI SDK:
  - `base_url="http://127.0.0.1:8045/v1"`
- Anthropic SDK:
  - `base_url="http://127.0.0.1:8045"`
- Gemini REST (`google-generativeai`):
  - `client_options={"api_endpoint": "http://127.0.0.1:8045"}`

Auth:
- Use `Authorization: Bearer <proxy_api_key>` when your proxy is configured with keys.

## 3) Model Discovery

Before sending requests, discover models dynamically:
- `GET /v1/models`

Do not hardcode model lists if your app must survive proxy/account updates.

## 4) Thinking Configuration

### OpenAI-style requests

Use `thinking` in request body:
- `thinking.type`: `enabled` or `disabled`
- `thinking.budget_tokens`: numeric budget

Typical budget mapping:
- `none -> 0`
- `low -> 4096`
- `medium -> 8192`
- `high -> 24576`

Example payload fragment:
```json
{
  "thinking": {
    "type": "enabled",
    "budget_tokens": 8192
  }
}
```

### Gemini v1beta compatibility

Some clients send:
- `generationConfig.thinkingConfig.thinkingLevel` as string (`NONE|LOW|MEDIUM|HIGH`)

Proxy behavior (modern versions) converts this to numeric `thinkingBudget` for internal paths.
This avoids Google internal API rejections that require numeric budget fields.

## 5) Streaming Contracts

### `/v1/chat/completions` stream

In SSE deltas (`choices[0].delta`):
- reasoning/thinking text: `reasoning_content`
- assistant output text: `content`
- tool calls: `tool_calls`

### `/v1/responses` stream

Expect lifecycle events such as:
- `response.created`
- `response.output_text.delta`
- `response.output_text.done`
- `response.completed`

For plain text output, aggregate `response.output_text.delta`.

## 6) Thinking Content vs Thinking Header

This distinction matters for UI design.

### Thinking content (raw reasoning stream)

- Source: `delta.reasoning_content`
- Nature: free-form model text, often multi-paragraph
- Use case: full “thinking pane”, logging, debug stream, trace export

### Thinking header (derived summary label)

- Not a dedicated protocol field
- It is client-derived UI text from thinking content
- Example strategy:
  - detect bold markdown headings in reasoning text (`**Header**`)
  - strip `**`
  - show latest unique header in compact status widget

Important:
- Header extraction is a heuristic, not guaranteed by protocol.
- Build graceful fallback when no extractable header appears.

## 7) Robust Header Parsing Rules

For reliable header extraction in real SSE streams:

1. Keep a carry-over buffer for `reasoning_content`.
2. Parse across chunk boundaries (a heading may be split over multiple events).
3. Extract only complete `**...**` segments (if that is your chosen convention).
4. Drop duplicates to avoid flicker.
5. Keep raw thinking content separately; do not mutate it for parsing.

## 8) Recommended Runtime State Flow (Generic)

For search/assistant UX:

1. `Transcribing speech` (if voice input)
2. `Sending API request`
3. `Thinking header/tool step updates` (if present)
4. `Live answer streaming view` on first output token
5. `Completed`

If no thinking signal appears:
- transition directly from `Sending API request` to live answer stream.

## 9) Fallback Strategy (Must-Have)

Implement both paths:

1. Streaming path (`stream=true`)
2. Non-stream fallback (`stream=false`) when:
   - stream setup fails
   - non-SSE content type is returned
   - transport errors occur

This is critical for reliability across environments and proxy/account states.

## 10) Minimal Integration Pattern (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8045/v1",
    api_key="sk-xxxx",
)

stream = client.chat.completions.create(
    model="gemini-3-flash",
    stream=True,
    messages=[{"role": "user", "content": "Hello"}],
    extra_body={
        "thinking": {
            "type": "enabled",
            "budget_tokens": 8192,
        }
    },
)

full_reasoning = []
full_answer = []

for chunk in stream:
    choice = chunk.choices[0]
    delta = choice.delta
    if getattr(delta, "reasoning_content", None):
        full_reasoning.append(delta.reasoning_content)
    if getattr(delta, "content", None):
        full_answer.append(delta.content)

reasoning_text = "".join(full_reasoning)
answer_text = "".join(full_answer)
```

## 11) Common Pitfalls

- Wrong OpenAI base URL (`/v1` missing).
- Assuming only `delta.content` exists (missing reasoning stream).
- Treating thinking header extraction as protocol-guaranteed.
- No stream fallback path.
- Hardcoded model list.

## 12) Quick Smoke Tests

Models:
```bash
curl -s http://127.0.0.1:8045/v1/models | jq
```

Streaming chat:
```bash
curl -N -X POST http://127.0.0.1:8045/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-xxxx" \
  -d '{
    "model":"gemini-3-flash",
    "stream":true,
    "messages":[{"role":"user","content":"hello"}],
    "thinking":{"type":"enabled","budget_tokens":4096}
  }'
```

## 13) Practical Checklist

- Discover models at startup (`/v1/models`).
- Expose runtime controls:
  - model
  - stream on/off
  - thinking level
- Aggregate two channels:
  - reasoning stream
  - answer stream
- Keep a header parser optional and heuristic-driven.
- Keep non-stream fallback always available.
