import json
import os
import urllib.error
import urllib.request

import pytest


def _normalize_base_url(value: str) -> str:
    text = (value or "").strip().rstrip("/")
    if not text:
        return "http://127.0.0.1:8045"
    if "://" not in text:
        return f"http://{text}"
    return text


def _safe_json_load(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def _json_request(method, url, payload=None, headers=None, timeout=25):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url=url, data=body, headers=req_headers, method=method.upper())

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers.items()), _safe_json_load(raw), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), _safe_json_load(raw), raw
    except Exception as exc:
        return 0, {}, None, str(exc)


def _extract_models(payload):
    if not isinstance(payload, dict):
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            out.append(item["id"])
    return out


def _choose_model(models):
    candidates = ["gemini-3-flash", "gemini-2.5-flash", "gemini-3-pro", "gemini-3.1-pro"]
    for candidate in candidates:
        if candidate in models:
            return candidate
    return models[0] if models else None


@pytest.fixture(scope="module")
def proxy_ctx():
    base_url = _normalize_base_url(os.getenv("ANTIGRAVITY_PROXY_URL", "http://127.0.0.1:8045"))
    api_key = os.getenv("ANTIGRAVITY_PROXY_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    health_status, _, _, health_raw = _json_request("GET", f"{base_url}/healthz", headers=headers)
    if health_status != 200:
        pytest.skip(f"Antigravity proxy not available at {base_url}: status={health_status}, raw={health_raw[:140]}")

    models_status, _, models_payload, models_raw = _json_request("GET", f"{base_url}/v1/models", headers=headers)
    if models_status != 200:
        pytest.skip(f"Proxy /v1/models unavailable: status={models_status}, raw={models_raw[:140]}")

    models = _extract_models(models_payload)
    model = _choose_model(models)
    if not model:
        pytest.skip("No model available in /v1/models")

    return {
        "base_url": base_url,
        "headers": headers,
        "model": model,
    }


def test_chat_stream_emits_sse_data_lines(proxy_ctx):
    payload = {
        "model": proxy_ctx["model"],
        "stream": True,
        "messages": [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "Explain DNS cache in one sentence."},
        ],
    }

    req = urllib.request.Request(
        url=f"{proxy_ctx['base_url']}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **proxy_ctx["headers"]},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=35) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "event-stream" in content_type.lower()

        data_lines = 0
        saw_done = False
        for _ in range(220):
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if line.startswith("data:"):
                data_lines += 1
                if line == "data: [DONE]":
                    saw_done = True
                    break

        assert data_lines > 0, "Expected at least one SSE data line"
        assert saw_done is True, "Expected stream to terminate with data: [DONE]"


def test_responses_stream_emits_event_types(proxy_ctx):
    payload = {
        "model": proxy_ctx["model"],
        "stream": True,
        "instructions": "Be concise.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "What is HTTP 503?"}
                ],
            }
        ],
    }

    req = urllib.request.Request(
        url=f"{proxy_ctx['base_url']}/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **proxy_ctx["headers"]},
        method="POST",
    )

    seen_types = set()
    with urllib.request.urlopen(req, timeout=35) as resp:
        assert resp.status == 200
        content_type = resp.headers.get("Content-Type", "")
        assert "event-stream" in content_type.lower()

        for _ in range(260):
            raw = resp.readline()
            if not raw:
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data: "):
                continue
            payload_txt = line[len("data: ") :].strip()
            if payload_txt == "[DONE]":
                break
            parsed = _safe_json_load(payload_txt)
            if not isinstance(parsed, dict):
                continue
            event_type = parsed.get("type")
            if isinstance(event_type, str) and event_type:
                seen_types.add(event_type)

    assert "response.created" in seen_types
    assert "response.completed" in seen_types
