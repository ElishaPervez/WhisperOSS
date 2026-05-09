#!/usr/bin/env python3
"""Probe Gemini/Gemma streaming thought parts via the raw REST API.

Usage:
  python3 scripts/gemini_thought_stream_probe.py --api-key "$GEMINI_API_KEY"

The script intentionally does not depend on google-genai so it can show the
actual streamed REST payload shape the app would need to consume.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


DEFAULT_PROMPT = (
    "Solve this logic puzzle concisely: Alice, Bob, and Carol each live in a "
    "different house on the same street: red, green, and blue. The person who "
    "lives in the red house owns a cat. Bob does not live in the green house. "
    "Carol owns a dog. The green house is to the left of the red house. Alice "
    "does not own a cat. Who lives in each house, and what pet do they own?"
)


def _iter_sse_payloads(response) -> Any:
    event_lines: list[str] = []
    for raw_line in response:
        line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
        if not line:
            if event_lines:
                for event_line in event_lines:
                    if event_line.startswith("data:"):
                        yield event_line[5:].strip()
                event_lines = []
            continue
        event_lines.append(line)

    if event_lines:
        for event_line in event_lines:
            if event_line.startswith("data:"):
                yield event_line[5:].strip()


def _part_dict(part: Any) -> dict[str, Any]:
    return part if isinstance(part, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", default="models/gemma-4-31b-it")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=-1,
        help="Set >=0 to send thinkingBudget; default omits it.",
    )
    parser.add_argument("--no-google-search", action="store_true")
    parser.add_argument("--raw", action="store_true", help="Print full JSON chunks too.")
    args = parser.parse_args()

    model_id = args.model.removeprefix("models/")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:streamGenerateContent?alt=sse"
    )
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": args.prompt}],
            }
        ],
        "generationConfig": {
            "thinkingConfig": {
                "includeThoughts": True,
            }
        },
    }
    if not args.no_google_search:
        payload["tools"] = [{"googleSearch": {}}]

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": args.api_key,
        },
        method="POST",
    )

    thought_text = ""
    answer_text = ""
    chunk_count = 0
    thought_part_count = 0
    answer_part_count = 0

    print(f"POST {url}")
    thinking_config = payload["generationConfig"]["thinkingConfig"]
    if int(args.thinking_budget) >= 0:
        thinking_config["thinkingBudget"] = int(args.thinking_budget)
    print(f"model={args.model} thinkingConfig={json.dumps(thinking_config, sort_keys=True)}")
    print()

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            for data in _iter_sse_payloads(response):
                if data == "[DONE]":
                    break
                chunk_count += 1
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    print(f"[raw non-json] {data[:500]}")
                    continue

                if args.raw:
                    print("[raw chunk]")
                    print(json.dumps(chunk, indent=2, ensure_ascii=False))

                candidates = chunk.get("candidates") or []
                for candidate in candidates:
                    content = candidate.get("content") or {}
                    for part in content.get("parts") or []:
                        part_obj = _part_dict(part)
                        keys = ",".join(sorted(part_obj.keys()))
                        text = str(part_obj.get("text") or "")
                        is_thought = bool(part_obj.get("thought"))
                        prefix = "THOUGHT" if is_thought else "ANSWER"
                        if is_thought:
                            thought_part_count += 1
                            thought_text += text
                        else:
                            answer_part_count += 1
                            answer_text += text
                        preview = text.replace("\n", "\\n")[:240]
                        print(f"[{prefix} part keys={keys}] {preview}")

                usage = chunk.get("usageMetadata") or {}
                if usage:
                    print(f"[usage] {json.dumps(usage, sort_keys=True)}")

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1

    print()
    print("summary:")
    print(f"  chunks={chunk_count}")
    print(f"  thought_parts={thought_part_count}")
    print(f"  answer_parts={answer_part_count}")
    print(f"  thought_chars={len(thought_text)}")
    print(f"  answer_chars={len(answer_text)}")
    if thought_text:
        print(f"  thought_preview={thought_text.replace(chr(10), ' ')[:500]}")
    if answer_text:
        print(f"  answer_preview={answer_text.replace(chr(10), ' ')[:500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
