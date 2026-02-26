#!/usr/bin/env python3
"""
Probe Antigravity proxy streaming behavior and extract "current step" signals.

This script is designed to answer one question before UI work:
What streaming markers are actually available from the proxy for live widget updates?

Scenarios covered:
- chat_reasoning: OpenAI chat/completions SSE (checks reasoning/tool/content deltas)
- chat_search: OpenAI chat/completions SSE with web_search tool marker
- responses_codex: OpenAI responses-style SSE (/v1/responses)
- completions_codex: OpenAI responses-style payload over /v1/completions

Usage examples:
  python scripts/proxy_streaming_probe.py
  python scripts/proxy_streaming_probe.py --api-key sk-... --json
  python scripts/proxy_streaming_probe.py --scenario chat_reasoning --max-events 120
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Iterable, List, Optional, Tuple


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
    if not payload:
        return []
    items = payload.get("data")
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            out.append(item["id"])
    return out


def _choose_first_available(models: List[str], candidates: List[str]) -> Optional[str]:
    for candidate in candidates:
        if candidate in models:
            return candidate
    return None


def _choose_thinking_candidate(models: List[str]) -> Optional[str]:
    for model in models:
        lowered = model.lower()
        if "thinking" in lowered:
            return model
    return _choose_first_available(
        models,
        [
            "gemini-3.1-pro",
            "gemini-3-pro",
            "gemini-2.5-pro",
            "gemini-3-flash",
            "gemini-2.5-flash",
        ],
    )


def _make_headers(api_key: str) -> Dict[str, str]:
    key = (api_key or "").strip()
    if not key:
        return {}
    return {"Authorization": f"Bearer {key}"}


def _is_search_marker(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "已为您搜索" in text
        or "来源引文" in text
        or "grounding" in lowered
        or "search query" in lowered
        or "vertexaisearch" in lowered
    )


def _extract_tool_names(delta: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return names
    for tool in tool_calls:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return names


def _classify_step_from_payload(payload: Dict[str, Any], raw_data: str) -> Tuple[Optional[str], Optional[str], Dict[str, Any]]:
    """Return (step, detail, signal_flags)."""
    flags = {
        "reasoning": False,
        "tool_calls": False,
        "search_grounding": False,
        "thought_signature": False,
    }

    raw_lower = (raw_data or "").lower()
    if "thoughtsignature" in raw_lower or "thought_signature" in raw_lower:
        flags["thought_signature"] = True

    # Codex/Responses style
    event_type = payload.get("type")
    if isinstance(event_type, str) and event_type:
        if event_type == "response.created":
            return "starting", "response.created", flags
        if event_type == "response.output_item.added":
            return "preparing_output", "response.output_item.added", flags
        if event_type == "response.content_part.added":
            return "starting_content", "response.content_part.added", flags
        if event_type == "response.output_text.delta":
            delta_text = payload.get("delta")
            if isinstance(delta_text, str) and _is_search_marker(delta_text):
                flags["search_grounding"] = True
                return "searching_web", "grounding delta", flags
            return "generating_answer", "output_text.delta", flags
        if event_type == "response.output_text.done":
            text = payload.get("text")
            if isinstance(text, str) and _is_search_marker(text):
                flags["search_grounding"] = True
            return "finalizing", "output_text.done", flags
        if event_type == "response.completed":
            return "completed", "response.completed", flags

    # OpenAI chat chunk style
    if isinstance(payload.get("error"), dict):
        message = payload["error"].get("message")
        detail = str(message)[:120] if message is not None else "stream error"
        return "error", detail, flags

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        delta = choice0.get("delta") if isinstance(choice0, dict) else {}
        if isinstance(delta, dict):
            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():
                flags["reasoning"] = True
                return "thinking", reasoning.strip()[:90], flags

            tool_names = _extract_tool_names(delta)
            if tool_names:
                flags["tool_calls"] = True
                return "calling_tool", ", ".join(tool_names[:3]), flags

            content = delta.get("content")
            if isinstance(content, str) and content:
                if _is_search_marker(content):
                    flags["search_grounding"] = True
                    return "searching_web", "grounding/citations", flags
                return "generating_answer", content[:90], flags

        finish_reason = choice0.get("finish_reason") if isinstance(choice0, dict) else None
        if isinstance(finish_reason, str) and finish_reason:
            return "finalizing", f"finish_reason={finish_reason}", flags

    return None, None, flags


def _summarize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "total_events": len(events),
        "data_events": 0,
        "done_events": 0,
        "comment_events": 0,
        "parse_errors": 0,
        "has_reasoning_content": False,
        "has_tool_calls": False,
        "has_search_grounding": False,
        "has_thought_signature": False,
        "tool_names": [],
        "event_types": {},
        "step_timeline": [],
        "reasoning_preview": "",
        "content_preview": "",
    }

    tool_set = set()
    current_step = ""

    for index, event in enumerate(events):
        kind = event.get("kind")
        t_ms = int(event.get("t_ms", 0))

        if kind == "comment":
            summary["comment_events"] += 1
            continue

        if kind != "data":
            continue

        summary["data_events"] += 1
        raw_data = str(event.get("data", ""))
        if raw_data == "[DONE]":
            summary["done_events"] += 1
            if current_step != "completed":
                summary["step_timeline"].append(
                    {"event_index": index, "t_ms": t_ms, "step": "completed", "detail": "[DONE]"}
                )
                current_step = "completed"
            continue

        payload = event.get("json")
        if not isinstance(payload, dict):
            summary["parse_errors"] += 1
            continue

        event_type = payload.get("type")
        if isinstance(event_type, str) and event_type:
            summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1

        step, detail, flags = _classify_step_from_payload(payload, raw_data)
        if flags["reasoning"]:
            summary["has_reasoning_content"] = True
            if not summary["reasoning_preview"]:
                summary["reasoning_preview"] = detail or ""
        if flags["tool_calls"]:
            summary["has_tool_calls"] = True
            choices = payload.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                delta = choices[0].get("delta")
                if isinstance(delta, dict):
                    for name in _extract_tool_names(delta):
                        tool_set.add(name)
        if flags["search_grounding"]:
            summary["has_search_grounding"] = True
        if flags["thought_signature"]:
            summary["has_thought_signature"] = True

        if not summary["content_preview"]:
            choices = payload.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                delta = choices[0].get("delta")
                if isinstance(delta, dict):
                    content = delta.get("content")
                    if isinstance(content, str) and content.strip():
                        summary["content_preview"] = content.strip()[:140]
            elif isinstance(payload.get("delta"), str):
                summary["content_preview"] = str(payload.get("delta"))[:140]

        if step and step != current_step:
            summary["step_timeline"].append(
                {
                    "event_index": index,
                    "t_ms": t_ms,
                    "step": step,
                    "detail": (detail or "")[:120],
                }
            )
            current_step = step

    summary["tool_names"] = sorted(tool_set)
    return summary


def _stream_request(
    method: str,
    url: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    timeout: float,
    max_events: int,
    max_seconds: float,
    raw_preview_lines: int,
) -> Tuple[int, Dict[str, str], List[Dict[str, Any]], str]:
    request_headers = {"Content-Type": "application/json"}
    request_headers.update(headers)

    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method=method.upper(),
    )

    events: List[Dict[str, Any]] = []
    preview_lines: List[str] = []

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            started = time.time()
            current_event = "message"
            data_lines: List[str] = []

            def flush_data_event(now_ms: int) -> None:
                nonlocal current_event, data_lines
                if not data_lines:
                    return
                data_text = "\n".join(data_lines).strip()
                row: Dict[str, Any] = {
                    "kind": "data",
                    "event": current_event,
                    "data": data_text,
                    "t_ms": now_ms,
                }
                if data_text and data_text != "[DONE]":
                    parsed = _safe_json_load(data_text)
                    if parsed is not None:
                        row["json"] = parsed
                events.append(row)
                current_event = "message"
                data_lines = []

            while True:
                elapsed = time.time() - started
                if elapsed >= max_seconds:
                    events.append(
                        {
                            "kind": "meta",
                            "event": "timeout",
                            "data": f"stopped after {max_seconds:.1f}s",
                            "t_ms": int(elapsed * 1000),
                        }
                    )
                    break
                if len(events) >= max_events:
                    events.append(
                        {
                            "kind": "meta",
                            "event": "max_events",
                            "data": f"stopped after {max_events} events",
                            "t_ms": int(elapsed * 1000),
                        }
                    )
                    break

                raw = resp.readline()
                if not raw:
                    flush_data_event(int((time.time() - started) * 1000))
                    break

                line = raw.decode("utf-8", errors="replace")
                if len(preview_lines) < max(1, raw_preview_lines):
                    preview_lines.append(line.rstrip("\r\n"))

                stripped = line.rstrip("\r\n")
                now_ms = int((time.time() - started) * 1000)

                if stripped == "":
                    flush_data_event(now_ms)
                    continue
                if stripped.startswith(":"):
                    events.append(
                        {
                            "kind": "comment",
                            "event": "comment",
                            "data": stripped,
                            "t_ms": now_ms,
                        }
                    )
                    continue
                if stripped.startswith("event:"):
                    current_event = stripped[6:].strip() or "message"
                    continue
                if stripped.startswith("data:"):
                    data_lines.append(stripped[5:].lstrip())
                    continue

            return resp.status, dict(resp.headers.items()), events, "\n".join(preview_lines)

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), [], raw
    except Exception as exc:
        return 0, {}, [], str(exc)


def _build_chat_payload(model: str, user_prompt: str, include_web_tool: bool, include_thinking: bool) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "stream": True,
        "temperature": 0.0,
        "messages": [
            {
                "role": "system",
                "content": "Be concise and explicit about each step.",
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
    }
    if include_web_tool:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                    },
                },
            }
        ]
    if include_thinking:
        payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": 2048,
        }
    return payload


def _build_responses_payload(model: str, prompt: str) -> Dict[str, Any]:
    return {
        "model": model,
        "stream": True,
        "instructions": "Be concise and explicit about each step.",
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt,
                    }
                ],
            }
        ],
    }


def _scenario_specs(models: List[str], forced_model: Optional[str]) -> List[Dict[str, Any]]:
    chat_default = _choose_first_available(
        models,
        [
            "gemini-3-flash",
            "gemini-2.5-flash",
            "gemini-3-pro",
            "gemini-3.1-pro",
        ],
    )
    thinking_model = _choose_thinking_candidate(models) or chat_default

    selected_chat = forced_model or chat_default
    selected_thinking = forced_model or thinking_model
    selected_codex = forced_model or chat_default

    return [
        {
            "name": "chat_reasoning",
            "endpoint": "/v1/chat/completions",
            "model": selected_thinking,
            "payload": lambda m: _build_chat_payload(
                m,
                "Reason step-by-step: why can stale DNS cache break app logins? End with one concrete fix command.",
                include_web_tool=False,
                include_thinking=True,
            ),
        },
        {
            "name": "chat_search",
            "endpoint": "/v1/chat/completions",
            "model": selected_chat,
            "payload": lambda m: _build_chat_payload(
                m,
                "Find the latest Python 3 stable release and include release date.",
                include_web_tool=True,
                include_thinking=False,
            ),
        },
        {
            "name": "responses_codex",
            "endpoint": "/v1/responses",
            "model": selected_codex,
            "payload": lambda m: _build_responses_payload(
                m,
                "Summarize what DNS is in 1 sentence.",
            ),
        },
        {
            "name": "completions_codex",
            "endpoint": "/v1/completions",
            "model": selected_codex,
            "payload": lambda m: _build_responses_payload(
                m,
                "Summarize what HTTP 503 means in 1 sentence.",
            ),
        },
    ]


def run_probe(
    base_url: str,
    api_key: str,
    timeout: float,
    max_events: int,
    max_seconds: float,
    raw_preview_lines: int,
    scenarios: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    headers = _make_headers(api_key)

    health_status, _, health_json, health_raw = _json_request(
        "GET", f"{base_url}/healthz", headers=headers, timeout=timeout
    )

    models_status, _, models_json, models_raw = _json_request(
        "GET", f"{base_url}/v1/models", headers=headers, timeout=timeout
    )
    models = _extract_models(models_json)

    scenario_specs = _scenario_specs(models, model)
    selected = set(scenarios or [s["name"] for s in scenario_specs])

    runs: List[Dict[str, Any]] = []
    for spec in scenario_specs:
        if spec["name"] not in selected:
            continue

        chosen_model = spec["model"]
        if not chosen_model:
            runs.append(
                {
                    "scenario": spec["name"],
                    "endpoint": spec["endpoint"],
                    "status": 0,
                    "error": "No suitable model found in /v1/models",
                }
            )
            continue

        payload = spec["payload"](chosen_model)
        status, response_headers, events, raw_preview = _stream_request(
            "POST",
            f"{base_url}{spec['endpoint']}",
            payload=payload,
            headers=headers,
            timeout=timeout,
            max_events=max_events,
            max_seconds=max_seconds,
            raw_preview_lines=raw_preview_lines,
        )

        row: Dict[str, Any] = {
            "scenario": spec["name"],
            "endpoint": spec["endpoint"],
            "model": chosen_model,
            "status": status,
            "mapped_model": response_headers.get("X-Mapped-Model")
            or response_headers.get("x-mapped-model", ""),
            "content_type": response_headers.get("Content-Type")
            or response_headers.get("content-type", ""),
            "request_payload": payload,
            "raw_preview": raw_preview,
        }

        if status == 200:
            row["summary"] = _summarize_events(events)
            row["events_sample"] = events[: min(20, len(events))]
        else:
            row["error"] = raw_preview[:500]

        runs.append(row)

    return {
        "base_url": base_url,
        "healthz": {
            "status": health_status,
            "json": health_json,
            "raw_preview": health_raw[:220],
        },
        "models": {
            "status": models_status,
            "count": len(models),
            "sample": models[:30],
            "raw_preview": models_raw[:220],
        },
        "runs": runs,
    }


def _print_report(result: Dict[str, Any]) -> None:
    print(f"Base URL: {result.get('base_url', '')}")
    health = result.get("healthz", {})
    models = result.get("models", {})
    print(
        "Healthz: "
        f"{health.get('status')} | Models: {models.get('status')} ({models.get('count')} models)"
    )

    for run in result.get("runs", []):
        print("\n" + "=" * 72)
        print(
            f"Scenario: {run.get('scenario')} | endpoint={run.get('endpoint')} "
            f"| status={run.get('status')} | model={run.get('model')}"
        )
        mapped = run.get("mapped_model") or "-"
        ctype = run.get("content_type") or "-"
        print(f"Mapped: {mapped} | Content-Type: {ctype}")

        if run.get("status") != 200:
            print(f"Error: {run.get('error', '')[:240]}")
            continue

        summary = run.get("summary", {})
        print(
            "Signals: "
            f"reasoning={str(summary.get('has_reasoning_content')).lower()} "
            f"tool_calls={str(summary.get('has_tool_calls')).lower()} "
            f"search_grounding={str(summary.get('has_search_grounding')).lower()} "
            f"thought_signature={str(summary.get('has_thought_signature')).lower()}"
        )
        if summary.get("tool_names"):
            print("Tool names: " + ", ".join(summary.get("tool_names", [])))

        print(
            "Events: "
            f"total={summary.get('total_events')} "
            f"data={summary.get('data_events')} "
            f"comments={summary.get('comment_events')} "
            f"done={summary.get('done_events')}"
        )

        timeline = summary.get("step_timeline", [])
        print("Step timeline:")
        if not timeline:
            print("  - (no step transitions detected)")
        else:
            for item in timeline[:20]:
                print(
                    f"  - +{item.get('t_ms', 0)}ms: {item.get('step')}"
                    f"  ({item.get('detail', '')})"
                )

        if summary.get("reasoning_preview"):
            print(f"Reasoning preview: {summary['reasoning_preview'][:140]}")
        if summary.get("content_preview"):
            print(f"Content preview: {summary['content_preview'][:140]}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe Antigravity proxy streaming and detect live step signals."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8045", help="Proxy base URL")
    parser.add_argument("--api-key", default="", help="Optional proxy API key")
    parser.add_argument("--timeout", type=float, default=35.0, help="HTTP timeout in seconds")
    parser.add_argument("--max-events", type=int, default=260, help="Max SSE events per scenario")
    parser.add_argument("--max-seconds", type=float, default=25.0, help="Max read duration per scenario")
    parser.add_argument("--raw-preview-lines", type=int, default=20, help="Number of raw stream lines to retain")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=["chat_reasoning", "chat_search", "responses_codex", "completions_codex"],
        help="Run specific scenario(s). Can be repeated.",
    )
    parser.add_argument("--model", default="", help="Force one model for all scenarios")
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    parser.add_argument("--json-out", default="", help="Optional path to write JSON result")
    args = parser.parse_args()

    result = run_probe(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout=args.timeout,
        max_events=max(20, int(args.max_events)),
        max_seconds=max(3.0, float(args.max_seconds)),
        raw_preview_lines=max(1, int(args.raw_preview_lines)),
        scenarios=args.scenario,
        model=(args.model or "").strip() or None,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_report(result)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nSaved JSON report to: {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
