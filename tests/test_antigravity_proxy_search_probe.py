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


def _json_request(method, url, payload=None, headers=None, timeout=20):
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=body,
        headers=request_headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers.items()), _safe_json_load(raw), raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), _safe_json_load(raw), raw
    except Exception as exc:
        return 0, {}, None, str(exc)


def _extract_models(models_payload):
    if not isinstance(models_payload, dict):
        return []
    items = models_payload.get("data")
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            out.append(item["id"])
    return out


def _choose_model(available, candidates):
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _chat_payload(model, query, use_tool_marker=False):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "stream": False,
    }
    if use_tool_marker:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search web",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
    return payload


def _is_transient_capacity_issue(status, raw):
    text = (raw or "").lower()
    return status in (429, 503) or (
        "token error" in text
        or "no accounts available with quota" in text
        or "all accounts exhausted" in text
        or "quota exhausted" in text
    )


@pytest.fixture(scope="module")
def proxy_ctx():
    base_url = _normalize_base_url(os.getenv("ANTIGRAVITY_PROXY_URL", "http://127.0.0.1:8045"))
    api_key = os.getenv("ANTIGRAVITY_PROXY_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    health_status, _, _, health_raw = _json_request("GET", f"{base_url}/healthz", headers=headers)
    if health_status != 200:
        pytest.skip(f"Antigravity proxy not available at {base_url}: healthz status={health_status}, raw={health_raw[:120]}")

    models_status, _, models_payload, models_raw = _json_request("GET", f"{base_url}/v1/models", headers=headers)
    if models_status != 200:
        pytest.skip(f"Antigravity proxy /v1/models unavailable: status={models_status}, raw={models_raw[:120]}")

    return {
        "base_url": base_url,
        "headers": headers,
        "models": _extract_models(models_payload),
    }


def test_proxy_healthz(proxy_ctx):
    status, _, payload, raw = _json_request("GET", f"{proxy_ctx['base_url']}/healthz", headers=proxy_ctx["headers"])
    assert status == 200, raw
    assert isinstance(payload, dict)
    assert payload.get("status") == "ok"


def test_proxy_models_list(proxy_ctx):
    status, _, payload, raw = _json_request("GET", f"{proxy_ctx['base_url']}/v1/models", headers=proxy_ctx["headers"])
    assert status == 200, raw
    models = _extract_models(payload)
    assert models, "Expected at least one model in /v1/models"


def test_online_suffix_search_path_works(proxy_ctx):
    model = _choose_model(
        proxy_ctx["models"],
        ["gemini-2.5-flash", "gemini-3-flash", "gemini-3-pro"],
    )
    if not model:
        pytest.skip("No suitable test model found for -online test")

    status, headers, payload, raw = _json_request(
        "POST",
        f"{proxy_ctx['base_url']}/v1/chat/completions",
        payload=_chat_payload(f"{model}-online", "capital of france"),
        headers=proxy_ctx["headers"],
        timeout=30,
    )

    if _is_transient_capacity_issue(status, raw):
        pytest.skip(f"Transient proxy capacity issue for -online path: status={status}, raw={raw[:160]}")

    assert status == 200, raw
    assert isinstance(payload, dict)
    mapped_model = headers.get("X-Mapped-Model") or headers.get("x-mapped-model")
    assert mapped_model, "Expected X-Mapped-Model response header"

    choices = payload.get("choices")
    assert isinstance(choices, list) and choices, "Expected choices in completion response"


def test_web_search_tool_marker_path_works(proxy_ctx):
    model = _choose_model(
        proxy_ctx["models"],
        ["gemini-2.5-flash", "gemini-3-flash", "gemini-3-pro"],
    )
    if not model:
        pytest.skip("No suitable test model found for web_search tool-marker test")

    status, _, payload, raw = _json_request(
        "POST",
        f"{proxy_ctx['base_url']}/v1/chat/completions",
        payload=_chat_payload(model, "capital of france", use_tool_marker=True),
        headers=proxy_ctx["headers"],
        timeout=30,
    )

    if _is_transient_capacity_issue(status, raw):
        pytest.skip(f"Transient proxy capacity issue for tool-marker path: status={status}, raw={raw[:160]}")

    assert status == 200, raw
    assert isinstance(payload, dict)
    choices = payload.get("choices")
    assert isinstance(choices, list) and choices, "Expected choices in completion response"


def test_gpt_online_route_is_accepted_when_available(proxy_ctx):
    if "gpt-4o" not in proxy_ctx["models"]:
        pytest.skip("gpt-4o not available in proxy model list")

    status, headers, payload, raw = _json_request(
        "POST",
        f"{proxy_ctx['base_url']}/v1/chat/completions",
        payload=_chat_payload("gpt-4o-online", "capital of france"),
        headers=proxy_ctx["headers"],
        timeout=30,
    )

    if _is_transient_capacity_issue(status, raw):
        pytest.skip(f"Transient proxy capacity issue for gpt-4o-online path: status={status}, raw={raw[:160]}")

    assert status == 200, raw
    assert isinstance(payload, dict)
    mapped_model = headers.get("X-Mapped-Model") or headers.get("x-mapped-model")
    assert mapped_model, "Expected X-Mapped-Model response header"
    choices = payload.get("choices")
    assert isinstance(choices, list) and choices, "Expected choices in completion response"
