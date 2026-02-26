#!/usr/bin/env python3
"""
Trace one forced streaming request against Antigravity proxy with your actual system prompt.

Default behavior:
- Query: "how to make an egg"
- Endpoint: /v1/chat/completions (stream=true)
- Prompt: src.prompts.SYSTEM_PROMPT_SEARCH
- Thinking requested
- web_search tool included
- Optional forced tool choice

This is intended as a ground-truth debug utility: it prints raw SSE lines with timestamps
and a compact parsed summary of reasoning/tool/content markers.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow running this script directly from the repository root or scripts/ folder.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.prompts import SYSTEM_PROMPT_SEARCH


def _normalize_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        return "http://127.0.0.1:8045"
    if "://" not in cleaned:
        return f"http://{cleaned}"
    return cleaned


def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(text)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _json_request(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0,
) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    body: Optional[bytes] = None
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


def _extract_models(payload: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    out: List[str] = []
    for row in data:
        if isinstance(row, dict) and isinstance(row.get("id"), str):
            out.append(row["id"])
    return out


def _choose_model(models: List[str], forced_model: str) -> Optional[str]:
    model = (forced_model or "").strip()
    if model:
        return model

    # Prefer models likely to support both thinking and tool calls.
    preferred = [
        "gemini-3.1-pro",
        "gemini-3-pro",
        "gemini-2.5-pro",
        "gemini-3-flash",
        "gemini-2.5-flash",
    ]
    for candidate in preferred:
        if candidate in models:
            return candidate

    for name in models:
        lowered = name.lower()
        if "pro" in lowered and "online" not in lowered:
            return name

    return models[0] if models else None


def _contains_search_marker(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "search query" in lowered
        or "web_search" in lowered
        or "grounding" in lowered
        or "vertexai" in lowered
        or "来源引文" in text
        or "已为您搜索" in text
    )


def _extract_tool_names(delta: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return names
    for row in tool_calls:
        if not isinstance(row, dict):
            continue
        function = row.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def _build_payload(
    model: str,
    query: str,
    force_tool: bool,
    thinking_budget: int,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "stream": True,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_SEARCH},
            {"role": "user", "content": query},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ],
        "thinking": {
            "type": "enabled",
            "budget_tokens": max(256, int(thinking_budget)),
        },
    }

    if force_tool:
        payload["tool_choice"] = {
            "type": "function",
            "function": {"name": "web_search"},
        }

    return payload


def _stream_trace(
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
    max_lines: int,
    max_seconds: float,
    live_output: bool,
) -> Tuple[int, Dict[str, str], List[str], Dict[str, Any], str]:
    req_headers = {"Content-Type": "application/json"}
    req_headers.update(headers)
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="POST",
    )

    raw_lines: List[str] = []
    summary: Dict[str, Any] = {
        "done_seen": False,
        "data_events": 0,
        "parse_errors": 0,
        "reasoning_chunks": 0,
        "content_chunks": 0,
        "grounded_content_chunks": 0,
        "tool_calls": [],
        "step_timeline": [],
    }
    tool_set = set()
    last_step = ""

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            started = time.time()
            data_lines: List[str] = []
            current_event = "message"

            def _record_step(step: str, detail: str) -> None:
                nonlocal last_step
                if step == last_step:
                    return
                last_step = step
                step_row = {
                    "t_ms": int((time.time() - started) * 1000),
                    "step": step,
                    "detail": detail[:120],
                }
                summary["step_timeline"].append(step_row)
                if live_output:
                    print(
                        f"[STEP +{step_row['t_ms']:05d}ms] {step_row['step']}: {step_row['detail']}",
                        flush=True,
                    )

            def _consume_data_event(data_text: str) -> None:
                summary["data_events"] += 1
                if data_text == "[DONE]":
                    summary["done_seen"] = True
                    _record_step("done", "[DONE]")
                    return

                payload_json = _safe_json_load(data_text)
                if not isinstance(payload_json, dict):
                    summary["parse_errors"] += 1
                    return

                choices = payload_json.get("choices")
                if not isinstance(choices, list) or not choices:
                    return
                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                delta = choice0.get("delta") if isinstance(choice0, dict) else {}
                if not isinstance(delta, dict):
                    return

                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning.strip():
                    summary["reasoning_chunks"] += 1
                    _record_step("thinking", reasoning.strip()[:80])

                names = _extract_tool_names(delta)
                for name in names:
                    tool_set.add(name)
                if names:
                    _record_step("tool_call", ", ".join(names))

                content = delta.get("content")
                if isinstance(content, str) and content:
                    summary["content_chunks"] += 1
                    if _contains_search_marker(content):
                        summary["grounded_content_chunks"] += 1
                        _record_step("grounded_content", content[:80])
                    else:
                        _record_step("writing_answer", content[:80])

                finish_reason = choice0.get("finish_reason")
                if isinstance(finish_reason, str) and finish_reason:
                    _record_step("finish", finish_reason)

            while True:
                if len(raw_lines) >= max(20, int(max_lines)):
                    raw_lines.append("# [STOP] max_lines reached")
                    break
                if (time.time() - started) >= max(3.0, float(max_seconds)):
                    raw_lines.append(f"# [STOP] max_seconds reached ({max_seconds}s)")
                    break

                raw = resp.readline()
                if not raw:
                    if data_lines:
                        _consume_data_event("\n".join(data_lines).strip())
                    raw_lines.append("# [EOF]")
                    break

                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                t_ms = int((time.time() - started) * 1000)
                line_row = f"[{t_ms:05d}ms] {line}"
                raw_lines.append(line_row)
                if live_output:
                    print(line_row, flush=True)

                if line == "":
                    data_text = "\n".join(data_lines).strip()
                    data_lines = []
                    if data_text:
                        _consume_data_event(data_text)
                    if data_text == "[DONE]":
                        break
                    current_event = "message"
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    current_event = line[6:].strip() or "message"
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
                    continue
                if current_event:
                    continue

            summary["tool_calls"] = sorted(tool_set)
            return resp.status, dict(resp.headers.items()), raw_lines, summary, ""

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), raw_lines, summary, raw
    except Exception as exc:
        return 0, {}, raw_lines, summary, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Force a streaming trace for one query using SYSTEM_PROMPT_SEARCH."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8045")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--query", default="how to make an egg")
    parser.add_argument("--force-tool", action="store_true", help="Force tool_choice=web_search")
    parser.add_argument("--thinking-budget", type=int, default=2048)
    parser.add_argument("--timeout", type=float, default=35.0)
    parser.add_argument("--max-lines", type=int, default=550)
    parser.add_argument("--max-seconds", type=float, default=25.0)
    parser.add_argument(
        "--no-live",
        action="store_true",
        help="Disable live line-by-line output and only print summary at the end.",
    )
    parser.add_argument("--out", default="", help="Optional output path for raw SSE lines")
    parser.add_argument(
        "--print-payload",
        action="store_true",
        help="Print full request payload before sending",
    )
    args = parser.parse_args()

    base_url = _normalize_base_url(args.base_url)
    headers: Dict[str, str] = {}
    key = (args.api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    health_status, _, _, health_raw = _json_request(
        "GET",
        f"{base_url}/healthz",
        headers=headers,
        timeout=float(args.timeout),
    )
    if health_status != 200:
        print(f"healthz failed: status={health_status} raw={health_raw[:220]}")
        return 1

    models_status, _, models_json, models_raw = _json_request(
        "GET",
        f"{base_url}/v1/models",
        headers=headers,
        timeout=float(args.timeout),
    )
    if models_status != 200:
        print(f"models failed: status={models_status} raw={models_raw[:220]}")
        return 1

    model = _choose_model(_extract_models(models_json), args.model)
    if not model:
        print("No models available from /v1/models.")
        return 1

    payload = _build_payload(
        model=model,
        query=str(args.query or "").strip() or "how to make an egg",
        force_tool=bool(args.force_tool),
        thinking_budget=int(args.thinking_budget),
    )
    if args.print_payload:
        print("--- REQUEST PAYLOAD ---")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print()
    if not args.no_live:
        print("--- RAW SSE (LIVE) ---", flush=True)

    status, response_headers, raw_lines, summary, err = _stream_trace(
        url=f"{base_url}/v1/chat/completions",
        payload=payload,
        headers=headers,
        timeout=float(args.timeout),
        max_lines=int(args.max_lines),
        max_seconds=float(args.max_seconds),
        live_output=(not bool(args.no_live)),
    )

    print(f"base_url={base_url}")
    print("endpoint=/v1/chat/completions")
    print(f"status={status}")
    print(f"model={model}")
    print(
        "mapped_model="
        + (
            response_headers.get("X-Mapped-Model")
            or response_headers.get("x-mapped-model", "")
        )
    )
    print(
        "content_type="
        + (
            response_headers.get("Content-Type")
            or response_headers.get("content-type", "")
        )
    )
    print(f"force_tool={str(bool(args.force_tool)).lower()}")

    if status != 200:
        print(f"error={err[:500]}")
        return 1

    print("\n--- SUMMARY ---")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.no_live:
        print("\n--- RAW SSE ---")
        for line in raw_lines:
            print(line)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("\n".join(raw_lines) + "\n")
        print(f"\nSaved raw SSE to: {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
