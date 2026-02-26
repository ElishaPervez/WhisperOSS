#!/usr/bin/env python3
"""
Capture raw SSE output from Antigravity proxy endpoints.

Goal: ground-truth capture of exactly what the proxy emits on the wire.
No heuristics required.

Examples:
  python scripts/proxy_stream_raw_capture.py --scenario chat
  python scripts/proxy_stream_raw_capture.py --scenario responses --out .tmp/responses_raw.sse
  python scripts/proxy_stream_raw_capture.py --model gemini-3-flash --max-seconds 20
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple


def _normalize_base_url(base_url: str) -> str:
    text = (base_url or "").strip().rstrip("/")
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


def _json_request(method: str, url: str, payload=None, headers=None, timeout: float = 25.0):
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=body,
        headers=req_headers,
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


def _extract_models(payload) -> List[str]:
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


def _choose_model(models: List[str], preferred: List[str]) -> Optional[str]:
    for candidate in preferred:
        if candidate in models:
            return candidate
    return models[0] if models else None


def _stream_capture(
    url: str,
    payload: Dict,
    headers: Dict[str, str],
    timeout: float,
    max_lines: int,
    max_seconds: float,
) -> Tuple[int, Dict[str, str], List[str], str]:
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers)
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )

    lines: List[str] = []
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            start = time.time()
            while True:
                if len(lines) >= max_lines:
                    lines.append("# [STOP] max_lines reached")
                    break
                if (time.time() - start) >= max_seconds:
                    lines.append(f"# [STOP] max_seconds reached ({max_seconds}s)")
                    break

                raw = resp.readline()
                if not raw:
                    lines.append("# [EOF]")
                    break

                text = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                t_ms = int((time.time() - start) * 1000)
                lines.append(f"[{t_ms:05d}ms] {text}")
                if text.strip() == "data: [DONE]":
                    break

            return resp.status, dict(resp.headers.items()), lines, ""
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), [], raw
    except Exception as exc:
        return 0, {}, [], str(exc)


def _build_payload(model: str, scenario: str) -> Dict:
    if scenario == "chat":
        return {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": "Be concise."},
                {
                    "role": "user",
                    "content": "Think briefly then answer: why does DNS cache flush fix stale records?",
                },
            ],
            "thinking": {"type": "enabled", "budget_tokens": 1024},
        }

    if scenario == "chat_search":
        return {
            "model": model,
            "stream": True,
            "messages": [
                {"role": "system", "content": "Be concise."},
                {
                    "role": "user",
                    "content": "Find latest Node.js LTS version and release date.",
                },
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search web",
                        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                    },
                }
            ],
        }

    return {
        "model": model,
        "stream": True,
        "instructions": "Be concise.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Summarize HTTP 503 in one sentence."}
                ],
            }
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture raw SSE lines from Antigravity proxy")
    parser.add_argument("--base-url", default="http://127.0.0.1:8045")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--scenario", choices=["chat", "chat_search", "responses"], default="chat")
    parser.add_argument("--model", default="")
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--max-lines", type=int, default=400)
    parser.add_argument("--max-seconds", type=float, default=25.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    base_url = _normalize_base_url(args.base_url)
    headers: Dict[str, str] = {}
    key = (args.api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    health_status, _, _, health_raw = _json_request("GET", f"{base_url}/healthz", headers=headers, timeout=args.timeout)
    if health_status != 200:
        print(f"healthz failed: status={health_status} raw={health_raw[:180]}")
        return 1

    models_status, _, models_json, models_raw = _json_request("GET", f"{base_url}/v1/models", headers=headers, timeout=args.timeout)
    if models_status != 200:
        print(f"models failed: status={models_status} raw={models_raw[:180]}")
        return 1

    models = _extract_models(models_json)
    model = (args.model or "").strip() or _choose_model(
        models,
        ["gemini-3-flash", "gemini-2.5-flash", "gemini-3-pro", "gemini-3.1-pro"],
    )
    if not model:
        print("No model available in /v1/models")
        return 1

    endpoint = "/v1/chat/completions"
    if args.scenario == "responses":
        endpoint = "/v1/responses"

    payload = _build_payload(model, args.scenario)

    status, response_headers, lines, err = _stream_capture(
        f"{base_url}{endpoint}",
        payload,
        headers,
        timeout=args.timeout,
        max_lines=max(20, int(args.max_lines)),
        max_seconds=max(3.0, float(args.max_seconds)),
    )

    print(f"base_url={base_url}")
    print(f"endpoint={endpoint}")
    print(f"status={status}")
    print(f"model={model}")
    print(f"mapped_model={response_headers.get('X-Mapped-Model') or response_headers.get('x-mapped-model', '')}")
    print(f"content_type={response_headers.get('Content-Type') or response_headers.get('content-type', '')}")

    if status != 200:
        print(f"error={err[:500]}")
        return 1

    print("\n--- RAW SSE ---")
    for line in lines:
        print(line)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"\nSaved raw capture to: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
