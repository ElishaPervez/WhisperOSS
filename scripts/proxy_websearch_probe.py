#!/usr/bin/env python
"""
Probe Antigravity proxy web-search behavior from Python.

Usage:
  python scripts/proxy_websearch_probe.py
  python scripts/proxy_websearch_probe.py --api-key sk-... --query "latest ai news"
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def _normalize_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        return "http://127.0.0.1:8045"
    if "://" not in cleaned:
        return f"http://{cleaned}"
    return cleaned


def _json_request(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    data: Optional[bytes] = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=request_headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            parsed = _safe_json_load(raw)
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, parsed, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        parsed = _safe_json_load(raw)
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, parsed, raw
    except Exception as exc:
        return 0, {}, None, str(exc)


def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(text)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _extract_models(payload: Optional[Dict[str, Any]]) -> List[str]:
    if not payload:
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    models: List[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


def _find_first_available(available: List[str], candidates: List[str]) -> Optional[str]:
    for model in candidates:
        if model in available:
            return model
    return None


def _has_search_markers(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "已为您搜索" in text
        or "来源引文" in text
        or "vertexaisearch.cloud.google.com" in lowered
        or "grounding-api-redirect" in lowered
    )


def _extract_content(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return ""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content", "")
    return content if isinstance(content, str) else str(content)


def _chat_payload(model: str, query: str, use_tool_marker: bool = False) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
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
                    "description": "Search the web for fresh information",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ]
    return payload


def run_probe(base_url: str, api_key: str, query: str, timeout: float) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    auth_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    started_at = int(time.time())

    health_status, _, health_json, health_raw = _json_request(
        "GET",
        f"{base_url}/healthz",
        headers=auth_headers,
        timeout=timeout,
    )

    models_status, _, models_json, models_raw = _json_request(
        "GET",
        f"{base_url}/v1/models",
        headers=auth_headers,
        timeout=timeout,
    )
    models = _extract_models(models_json)

    selected_models = [
        _find_first_available(models, ["gemini-2.5-flash", "gemini-3-flash", "gemini-2.0-flash-exp"]),
        _find_first_available(models, ["gemini-3-pro", "gemini-3.1-pro", "gemini-3-pro-high"]),
        _find_first_available(models, ["claude-sonnet-4-6", "claude-sonnet-4-5", "claude-3-5-sonnet-20241022"]),
        _find_first_available(models, ["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]),
    ]
    selected_models = [m for m in selected_models if m]

    scenarios: List[Dict[str, Any]] = []
    for model in selected_models:
        case_specs = [
            ("plain", model, False),
            ("online_suffix", f"{model}-online", False),
            ("tool_marker", model, True),
        ]
        for case_name, requested_model, use_tool in case_specs:
            status, headers, body_json, body_raw = _json_request(
                "POST",
                f"{base_url}/v1/chat/completions",
                payload=_chat_payload(requested_model, query, use_tool_marker=use_tool),
                headers=auth_headers,
                timeout=timeout,
            )
            content = _extract_content(body_json)
            scenarios.append(
                {
                    "base_model": model,
                    "case": case_name,
                    "requested_model": requested_model,
                    "status": status,
                    "mapped_model": headers.get("x-mapped-model", ""),
                    "content_preview": content[:220],
                    "search_markers": _has_search_markers(content),
                    "raw_body_preview": body_raw[:220],
                }
            )

    mcp_status, _, mcp_json, mcp_raw = _json_request(
        "GET",
        f"{base_url}/mcp/web_search_prime/mcp",
        headers=auth_headers,
        timeout=timeout,
    )

    return {
        "started_at_epoch": started_at,
        "base_url": base_url,
        "healthz": {
            "status": health_status,
            "json": health_json,
            "raw_preview": health_raw[:220],
        },
        "models": {
            "status": models_status,
            "count": len(models),
            "sample": models[:25],
        },
        "selected_models_for_matrix": selected_models,
        "chat_matrix": scenarios,
        "mcp_web_search_probe": {
            "status": mcp_status,
            "json": mcp_json,
            "raw_preview": mcp_raw[:220],
        },
    }


def _print_summary(result: Dict[str, Any]) -> None:
    print(f"Base URL: {result['base_url']}")
    print(f"Healthz: {result['healthz']['status']}  Models: {result['models']['status']} ({result['models']['count']} models)")
    selected = result.get("selected_models_for_matrix", [])
    if not selected:
        print("No known test models found in /v1/models.")
        return

    print("\nChat Search Matrix:")
    for row in result.get("chat_matrix", []):
        print(
            f"- {row['base_model']:20s} | {row['case']:13s} | status={row['status']:3d} | "
            f"mapped={row['mapped_model'] or '-':18s} | search_markers={str(row['search_markers']).lower()}"
        )

    print(
        "\nMCP endpoint probe: "
        f"/mcp/web_search_prime/mcp -> status={result['mcp_web_search_probe']['status']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Antigravity proxy web-search behavior.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8045", help="Proxy base URL")
    parser.add_argument("--api-key", default="", help="Optional proxy API key")
    parser.add_argument("--query", default="capital of france", help="Query used for chat matrix")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout seconds")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    args = parser.parse_args()

    result = run_probe(
        base_url=args.base_url,
        api_key=args.api_key,
        query=args.query,
        timeout=args.timeout,
    )

    _print_summary(result)
    if args.json:
        print("\nFull JSON:")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    health_status = int(result.get("healthz", {}).get("status", 0))
    return 0 if health_status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
