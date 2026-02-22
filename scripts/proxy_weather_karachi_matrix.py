#!/usr/bin/env python
"""
Run a Karachi weather accuracy matrix against Antigravity proxy models.

This script compares model outputs to a user-defined target baseline
and reports which models/cases are close enough.

Examples:
  python scripts/proxy_weather_karachi_matrix.py
  python scripts/proxy_weather_karachi_matrix.py --all-models
  python scripts/proxy_weather_karachi_matrix.py --models gemini-3-flash gemini-2.5-flash
  python scripts/proxy_weather_karachi_matrix.py --target-temp 26 --target-humidity 55 --target-precip 0
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


DEFAULT_QUERY = (
    "What is the weather in Karachi right now? "
    "Give current temperature in Celsius, humidity percentage, "
    "and precipitation chance percentage in one short answer."
)

SYSTEM_PROMPT = (
    "Return ONLY one compact JSON object with keys "
    "temp_c, humidity_pct, precip_pct. "
    "No markdown, no prose, no code fences."
)


@dataclass
class Metrics:
    temp_c: Optional[float]
    humidity_pct: Optional[float]
    precip_pct: Optional[float]


@dataclass
class EvalResult:
    model: str
    case: str
    status: int
    mapped_model: str
    used_search_markers: bool
    metrics: Metrics
    temp_ok: bool
    humidity_ok: bool
    precip_ok: bool
    overall_ok: bool
    raw_preview: str


def _normalize_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        return "http://127.0.0.1:8045"
    if "://" not in cleaned:
        return f"http://{cleaned}"
    return cleaned


def _safe_json_load(raw: str) -> Optional[Dict[str, Any]]:
    try:
        value = json.loads(raw)
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def _json_request(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 35.0,
) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
    request_headers: Dict[str, str] = {"Content-Type": "application/json"}
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
    models: List[str] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            models.append(item["id"])
    return models


def _filter_weather_candidate_models(all_models: Sequence[str]) -> List[str]:
    out: List[str] = []
    for model in all_models:
        m = model.strip()
        if not m:
            continue
        if "*" in m:
            continue
        low = m.lower()
        # Skip non-text / irrelevant routes.
        if "image" in low:
            continue
        if "internal-background-task" in low:
            continue
        # Keep common text model families only.
        if not (
            low.startswith("gemini")
            or low.startswith("claude")
            or low.startswith("gpt")
            or low.startswith("o1")
            or low.startswith("o3")
        ):
            continue
        out.append(m)
    return out


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


def _has_search_markers(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "已为您搜索" in text
        or "来源引文" in text
        or "grounding-api-redirect" in lowered
        or "vertexaisearch.cloud.google.com" in lowered
    )


def _extract_temp_c(text: str) -> Optional[float]:
    # Prefer explicit Celsius mentions.
    patterns = [
        r"temp(?:erature)?_?c\"?\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        r"(-?\d+(?:\.\d+)?)\s*°\s*c\b",
        r"(-?\d+(?:\.\d+)?)\s*celsius\b",
        r"temperature[^0-9-]{0,20}(-?\d+(?:\.\d+)?)\s*°?\s*c?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
    return None


def _extract_json_metrics(text: str) -> Metrics:
    # Try to parse the first JSON object that contains expected keys.
    candidates = re.findall(r"\{[^{}]{2,300}\}", text)
    for block in candidates:
        try:
            parsed = json.loads(block)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        if not any(k in parsed for k in ("temp_c", "temperature_c", "humidity_pct", "precip_pct")):
            continue

        def _to_float(value: Any) -> Optional[float]:
            try:
                if value is None:
                    return None
                return float(value)
            except Exception:
                return None

        temp = _to_float(parsed.get("temp_c", parsed.get("temperature_c")))
        humidity = _to_float(parsed.get("humidity_pct", parsed.get("humidity")))
        precip = _to_float(parsed.get("precip_pct", parsed.get("precipitation_pct", parsed.get("precipitation"))))
        return Metrics(temp_c=temp, humidity_pct=humidity, precip_pct=precip)

    return Metrics(temp_c=None, humidity_pct=None, precip_pct=None)


def _extract_humidity_pct(text: str) -> Optional[float]:
    patterns = [
        r"humidity(?:_pct)?\"?\s*[:=]\s*(\d{1,3}(?:\.\d+)?)",
        r"humidity[^0-9]{0,24}(\d{1,3}(?:\.\d+)?)\s*%",
        r"(\d{1,3}(?:\.\d+)?)\s*%\s*humidity",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
    return None


def _extract_precip_pct(text: str) -> Optional[float]:
    patterns = [
        r"precip(?:itation)?(?:_pct)?\"?\s*[:=]\s*(\d{1,3}(?:\.\d+)?)",
        r"precipitation[^0-9]{0,24}(\d{1,3}(?:\.\d+)?)\s*%",
        r"chance of rain[^0-9]{0,24}(\d{1,3}(?:\.\d+)?)\s*%",
        r"rain chance[^0-9]{0,24}(\d{1,3}(?:\.\d+)?)\s*%",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                pass
    return None


def _extract_metrics(text: str) -> Metrics:
    json_metrics = _extract_json_metrics(text)
    if (
        json_metrics.temp_c is not None
        or json_metrics.humidity_pct is not None
        or json_metrics.precip_pct is not None
    ):
        return json_metrics

    return Metrics(
        temp_c=_extract_temp_c(text),
        humidity_pct=_extract_humidity_pct(text),
        precip_pct=_extract_precip_pct(text),
    )


def _is_within(value: Optional[float], target: float, tolerance: float) -> bool:
    if value is None:
        return False
    return abs(value - target) <= tolerance


def _build_payload(model: str, query: str, case: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        "stream": False,
        "temperature": 0.0,
        "max_tokens": 640,
    }
    if case == "tool":
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web for current weather data.",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                    },
                },
            }
        ]
    return payload


def _eval_case(
    base_url: str,
    headers: Dict[str, str],
    model: str,
    case: str,
    query: str,
    timeout: float,
    target_temp: float,
    target_humidity: float,
    target_precip: float,
    temp_tol: float,
    humidity_tol: float,
    precip_tol: float,
) -> EvalResult:
    request_model = model if case == "tool" else f"{model}-online"
    status, resp_headers, body_json, raw = _json_request(
        method="POST",
        url=f"{base_url}/v1/chat/completions",
        payload=_build_payload(request_model, query, case),
        headers=headers,
        timeout=timeout,
    )

    mapped = resp_headers.get("X-Mapped-Model") or resp_headers.get("x-mapped-model", "")
    content = _extract_content(body_json)
    source_text = content if content else raw
    metrics = _extract_metrics(source_text)
    used_search = _has_search_markers(source_text)

    temp_ok = _is_within(metrics.temp_c, target_temp, temp_tol)
    humidity_ok = _is_within(metrics.humidity_pct, target_humidity, humidity_tol)
    precip_ok = _is_within(metrics.precip_pct, target_precip, precip_tol)
    overall_ok = temp_ok and humidity_ok and precip_ok

    preview = source_text.replace("\n", " ")[:240]
    return EvalResult(
        model=model,
        case=case,
        status=status,
        mapped_model=mapped,
        used_search_markers=used_search,
        metrics=metrics,
        temp_ok=temp_ok,
        humidity_ok=humidity_ok,
        precip_ok=precip_ok,
        overall_ok=overall_ok,
        raw_preview=preview,
    )


def run_matrix(
    base_url: str,
    api_key: str,
    query: str,
    models: Optional[Sequence[str]],
    all_models: bool,
    max_models: int,
    timeout: float,
    target_temp: float,
    target_humidity: float,
    target_precip: float,
    temp_tol: float,
    humidity_tol: float,
    precip_tol: float,
) -> Dict[str, Any]:
    base_url = _normalize_base_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    started_at = int(time.time())

    health_status, _, health_json, health_raw = _json_request(
        "GET", f"{base_url}/healthz", headers=headers, timeout=10
    )
    models_status, _, models_json, models_raw = _json_request(
        "GET", f"{base_url}/v1/models", headers=headers, timeout=15
    )
    discovered_models = _extract_models(models_json)
    candidate_models = _filter_weather_candidate_models(discovered_models)

    if models:
        selected = [m for m in models if m]
    elif all_models:
        selected = list(candidate_models)
    else:
        # Reasonable default set for weather validation.
        preferred = [
            "gemini-3-flash",
            "gemini-3.1-pro-high",
            "gemini-2.5-flash",
            "gpt-4o",
            "claude-sonnet-4-6",
            "claude-sonnet-4-6-thinking",
        ]
        selected = [m for m in preferred if m in candidate_models]
        if not selected:
            selected = candidate_models[:]

    if max_models > 0:
        selected = selected[:max_models]

    rows: List[EvalResult] = []
    for model in selected:
        for case in ("online", "tool"):
            row = _eval_case(
                base_url=base_url,
                headers=headers,
                model=model,
                case=case,
                query=query,
                timeout=timeout,
                target_temp=target_temp,
                target_humidity=target_humidity,
                target_precip=target_precip,
                temp_tol=temp_tol,
                humidity_tol=humidity_tol,
                precip_tol=precip_tol,
            )
            rows.append(row)

    out_rows = [
        {
            "model": r.model,
            "case": r.case,
            "status": r.status,
            "mapped_model": r.mapped_model,
            "used_search_markers": r.used_search_markers,
            "temp_c": r.metrics.temp_c,
            "humidity_pct": r.metrics.humidity_pct,
            "precip_pct": r.metrics.precip_pct,
            "temp_ok": r.temp_ok,
            "humidity_ok": r.humidity_ok,
            "precip_ok": r.precip_ok,
            "overall_ok": r.overall_ok,
            "raw_preview": r.raw_preview,
        }
        for r in rows
    ]

    summary = {
        "total_cases": len(rows),
        "http_200_cases": sum(1 for r in rows if r.status == 200),
        "overall_ok_cases": sum(1 for r in rows if r.overall_ok),
        "search_marker_cases": sum(1 for r in rows if r.used_search_markers),
    }

    return {
        "started_at_epoch": started_at,
        "base_url": base_url,
        "query": query,
        "targets": {
            "temp_c": target_temp,
            "humidity_pct": target_humidity,
            "precip_pct": target_precip,
            "temp_tolerance": temp_tol,
            "humidity_tolerance": humidity_tol,
            "precip_tolerance": precip_tol,
        },
        "healthz": {"status": health_status, "json": health_json, "raw_preview": health_raw[:180]},
        "models_endpoint": {
            "status": models_status,
            "count": len(discovered_models),
            "candidate_count": len(candidate_models),
            "selected_count": len(selected),
            "raw_preview": models_raw[:180],
        },
        "selected_models": selected,
        "results": out_rows,
        "summary": summary,
    }


def _fmt_num(value: Optional[float]) -> str:
    if value is None:
        return "-"
    if int(value) == value:
        return str(int(value))
    return f"{value:.1f}"


def _print_summary(payload: Dict[str, Any]) -> None:
    print(f"Base URL: {payload['base_url']}")
    print(
        f"Health: {payload['healthz']['status']} | "
        f"Models endpoint: {payload['models_endpoint']['status']} "
        f"(selected={payload['models_endpoint']['selected_count']})"
    )
    t = payload["targets"]
    print(
        "Target: "
        f"{t['temp_c']}°C ±{t['temp_tolerance']} | "
        f"Humidity {t['humidity_pct']}% ±{t['humidity_tolerance']} | "
        f"Precip {t['precip_pct']}% ±{t['precip_tolerance']}"
    )
    print("")
    print("Model | Case | HTTP | Search | TempC | Hum% | Precip% | T/H/P | Overall")
    print("-" * 92)
    for row in payload["results"]:
        checks = f"{'Y' if row['temp_ok'] else 'N'}/{'Y' if row['humidity_ok'] else 'N'}/{'Y' if row['precip_ok'] else 'N'}"
        print(
            f"{row['model'][:25]:25s} | "
            f"{row['case']:6s} | "
            f"{row['status']:4d} | "
            f"{('Y' if row['used_search_markers'] else 'N'):6s} | "
            f"{_fmt_num(row['temp_c']):5s} | "
            f"{_fmt_num(row['humidity_pct']):4s} | "
            f"{_fmt_num(row['precip_pct']):7s} | "
            f"{checks:5s} | "
            f"{'PASS' if row['overall_ok'] else 'FAIL'}"
        )

    s = payload["summary"]
    print("")
    print(
        "Summary: "
        f"cases={s['total_cases']} | "
        f"http200={s['http_200_cases']} | "
        f"search_markers={s['search_marker_cases']} | "
        f"overall_ok={s['overall_ok_cases']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Karachi weather model matrix via Antigravity proxy.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8045")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--models", nargs="*", default=None, help="Explicit model list.")
    parser.add_argument("--all-models", action="store_true", help="Run all concrete text models from /v1/models.")
    parser.add_argument("--max-models", type=int, default=12, help="Max models to evaluate (0 or negative = no limit).")
    parser.add_argument("--timeout", type=float, default=35.0)

    parser.add_argument("--target-temp", type=float, default=26.0)
    parser.add_argument("--target-humidity", type=float, default=55.0)
    parser.add_argument("--target-precip", type=float, default=0.0)

    parser.add_argument("--temp-tol", type=float, default=2.0)
    parser.add_argument("--humidity-tol", type=float, default=20.0)
    parser.add_argument("--precip-tol", type=float, default=15.0)

    parser.add_argument("--json", action="store_true", help="Print full JSON payload.")
    args = parser.parse_args()

    payload = run_matrix(
        base_url=args.base_url,
        api_key=args.api_key,
        query=args.query,
        models=args.models,
        all_models=args.all_models,
        max_models=args.max_models,
        timeout=args.timeout,
        target_temp=args.target_temp,
        target_humidity=args.target_humidity,
        target_precip=args.target_precip,
        temp_tol=args.temp_tol,
        humidity_tol=args.humidity_tol,
        precip_tol=args.precip_tol,
    )

    _print_summary(payload)
    if args.json:
        print("\nFull JSON:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if payload["healthz"]["status"] != 200:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
