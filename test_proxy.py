#!/usr/bin/env python3
"""
Interactive Textual + Rich TUI for Antigravity proxy (OpenAI SDK path).

Features:
- Live panes for:
  - Thinking stream
  - Text stream
  - Proxy stream events
- Commands:
  - /model <model>
  - /stream [on|off]
  - /thinking <high|medium|low|none>
  - /help
  - /clear
  - /quit

Default endpoint:
  http://127.0.0.1:8045/v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from threading import Thread
from typing import Any, Callable, Dict, List, Optional, Sequence

try:
    from openai import OpenAI
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit("Missing dependency: pip install openai") from exc

try:
    from rich.panel import Panel
    from rich.text import Text
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical
    from textual.widgets import Footer, Header, Input, RichLog, Static
except Exception as exc:  # pragma: no cover - import guard
    raise SystemExit("Missing dependencies: pip install textual rich") from exc

try:
    from src.prompts import SYSTEM_PROMPT_SEARCH
except Exception:
    SYSTEM_PROMPT_SEARCH = "You are a concise and helpful assistant."


THINKING_LEVELS = ("none", "low", "medium", "high")
THINKING_BUDGETS = {
    "none": 0,
    "low": 4096,
    "medium": 8192,
    "high": 24576,
}
STREAM_TOGGLE_VALUES = {
    "on": True,
    "off": False,
    "true": True,
    "false": False,
    "1": True,
    "0": False,
    "enable": True,
    "disable": False,
    "enabled": True,
    "disabled": False,
}


@dataclass
class Turn:
    role: str
    content: str


def _normalize_root_base_url(base_url: str) -> str:
    cleaned = (base_url or "").strip().rstrip("/")
    if not cleaned:
        return "http://127.0.0.1:8045"
    if "://" not in cleaned:
        cleaned = f"http://{cleaned}"
    if cleaned.endswith("/v1"):
        return cleaned[:-3]
    return cleaned


def _to_openai_base_url(root_base_url: str) -> str:
    root = _normalize_root_base_url(root_base_url)
    return f"{root}/v1"


def _thinking_extra_body(level: str) -> Dict[str, Any]:
    normalized = level.lower().strip()
    if normalized not in THINKING_LEVELS:
        normalized = "none"

    # Align with proxy source behavior: OpenAI path accepts `thinking` and maps to thinkingBudget.
    if normalized == "none":
        return {"thinking": {"type": "disabled", "budget_tokens": 0}}
    return {
        "thinking": {
            "type": "enabled",
            "budget_tokens": THINKING_BUDGETS[normalized],
        }
    }


def _merge_fragments(existing: str, fragment: str) -> str:
    base = str(existing or "")
    tail = str(fragment or "")
    if not base:
        return tail
    if not tail:
        return base
    if tail in base or base.endswith(tail):
        return base

    max_overlap = min(120, len(base), len(tail))
    for overlap in range(max_overlap, 12, -1):
        if base.endswith(tail[:overlap]):
            return base + tail[overlap:]

    if base[-1].isspace() or tail[0] in ".,;:!?)]}\n ":
        return base + tail
    return base + " " + tail


def _extract_tool_names(delta: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    tool_calls = delta.get("tool_calls")
    if not isinstance(tool_calls, list):
        return names
    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


class ProxySdkClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_sec: float = 90.0,
        max_tokens: int = 1400,
    ) -> None:
        self.root_base_url = _normalize_root_base_url(base_url)
        self.openai_base_url = _to_openai_base_url(base_url)
        self.api_key = (api_key or "").strip() or "sk-antigravity"
        self.timeout_sec = max(10.0, float(timeout_sec))
        self.max_tokens = max(128, int(max_tokens))
        self.client = OpenAI(
            base_url=self.openai_base_url,
            api_key=self.api_key,
            timeout=self.timeout_sec,
        )

    def _build_messages(self, prompt: str, history: Sequence[Turn]) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT_SEARCH}]
        for turn in history[-14:]:
            role = turn.role.lower().strip()
            content = turn.content.strip()
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": prompt})
        return messages

    def chat(
        self,
        prompt: str,
        history: Sequence[Turn],
        model: str,
        stream: bool,
        thinking_level: str,
        on_event: Callable[[str, str], None],
    ) -> str:
        messages = self._build_messages(prompt, history)
        extra_body = _thinking_extra_body(thinking_level)

        params: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "extra_body": extra_body,
        }

        if stream:
            return self._chat_streaming(params, on_event)
        return self._chat_non_streaming(params, on_event)

    def _chat_non_streaming(
        self, params: Dict[str, Any], on_event: Callable[[str, str], None]
    ) -> str:
        on_event("meta", "endpoint=/v1/chat/completions stream=false sdk=openai")
        resp = self.client.chat.completions.create(**params, stream=False)
        payload = resp.model_dump(exclude_none=True)
        on_event("raw", json.dumps(payload, ensure_ascii=False)[:700])

        choices = payload.get("choices", [])
        if not choices:
            raise RuntimeError("No choices in non-stream response")

        first = choices[0]
        message = first.get("message", {}) if isinstance(first, dict) else {}
        content = message.get("content", "") if isinstance(message, dict) else ""
        if not isinstance(content, str):
            content = str(content)

        reasoning = ""
        if isinstance(message, dict):
            rc = message.get("reasoning_content")
            if isinstance(rc, str):
                reasoning = rc

        if reasoning.strip():
            on_event("thinking", reasoning)
        if content.strip():
            on_event("text", content)
            return content
        raise RuntimeError("Empty assistant content in non-stream response")

    def _chat_streaming(
        self, params: Dict[str, Any], on_event: Callable[[str, str], None]
    ) -> str:
        on_event("meta", "endpoint=/v1/chat/completions stream=true sdk=openai")
        stream = self.client.chat.completions.create(**params, stream=True)

        text_buffer = ""
        thinking_buffer = ""
        event_counter = 0

        for chunk in stream:
            event_counter += 1
            chunk_dict = chunk.model_dump(exclude_none=True)
            if event_counter <= 45:
                on_event("raw", json.dumps(chunk_dict, ensure_ascii=False)[:700])

            choices = chunk_dict.get("choices", [])
            if not isinstance(choices, list) or not choices:
                continue
            choice0 = choices[0] if isinstance(choices[0], dict) else {}
            delta = choice0.get("delta", {}) if isinstance(choice0, dict) else {}
            if not isinstance(delta, dict):
                continue

            reasoning = delta.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                thinking_buffer = _merge_fragments(thinking_buffer, reasoning)
                on_event("thinking", thinking_buffer)

            tool_names = _extract_tool_names(delta)
            if tool_names:
                on_event("event", f"tool_call={tool_names[0]}")

            content = delta.get("content")
            if isinstance(content, str) and content:
                text_buffer = _merge_fragments(text_buffer, content)
                on_event("text", text_buffer)

            finish_reason = choice0.get("finish_reason")
            if isinstance(finish_reason, str) and finish_reason:
                on_event("event", f"finish_reason={finish_reason}")

        final_text = text_buffer.strip()
        if not final_text:
            raise RuntimeError("Streaming completed but no assistant text was emitted")
        return final_text


class ProxyTui(App):
    CSS = """
    #status {
        height: 3;
        margin: 0 1;
    }
    #panes {
        height: 1fr;
        margin: 0 1;
    }
    .pane {
        width: 1fr;
        border: round $panel;
        margin: 0 1 1 0;
    }
    .pane:last-child {
        margin-right: 0;
    }
    .pane_title {
        height: 1;
        padding: 0 1;
        color: $accent;
        text-style: bold;
    }
    .pane_body {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
    }
    #thinking_log {
        height: 1fr;
    }
    #text_log {
        height: 1fr;
    }
    #event_log {
        height: 1fr;
    }
    #prompt {
        margin: 0 1 1 1;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+l", "clear_views", "Clear"),
        ("f2", "toggle_stream", "Stream"),
        ("f3", "cycle_thinking", "Thinking"),
    ]

    def __init__(
        self,
        proxy_client: ProxySdkClient,
        model: str,
        stream_enabled: bool,
        thinking_level: str,
    ) -> None:
        super().__init__()
        self.proxy_client = proxy_client
        self.model = model.strip() or "gemini-3-flash"
        self.stream_enabled = bool(stream_enabled)
        self.thinking_level = (
            thinking_level.lower() if thinking_level.lower() in THINKING_LEVELS else "low"
        )
        self.history: List[Turn] = []
        self.busy = False
        self._thread: Optional[Thread] = None
        self._thinking_buffer = ""
        self._text_buffer = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(id="status")
        with Horizontal(id="panes"):
            with Vertical(classes="pane"):
                yield Static("", id="thinking_title", classes="pane_title")
                yield RichLog(
                    id="thinking_log",
                    classes="pane_body",
                    wrap=True,
                    markup=False,
                    highlight=False,
                    auto_scroll=True,
                )
            with Vertical(classes="pane"):
                yield Static("", id="text_title", classes="pane_title")
                yield RichLog(
                    id="text_log",
                    classes="pane_body",
                    wrap=True,
                    markup=False,
                    highlight=False,
                    auto_scroll=True,
                )
            with Vertical(classes="pane"):
                yield Static("Proxy Events", classes="pane_title")
                yield RichLog(id="event_log", wrap=True, markup=False, highlight=False)
        yield Input(
            placeholder=(
                "Prompt or command: /model <model> | /stream [on|off] | "
                "/thinking <high|medium|low|none> | /help"
            ),
            id="prompt",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_pane_titles()
        self._reset_stream_panes()
        self._refresh_status()
        self._log("Ready. Commands: /help", style="green")
        self.query_one("#prompt", Input).focus()

    def _refresh_status(self) -> None:
        stream_state = "on" if self.stream_enabled else "off"
        state = "busy" if self.busy else "idle"
        status_text = (
            f"root={self.proxy_client.root_base_url} | openai_base={self.proxy_client.openai_base_url} | "
            f"model={self.model} | stream={stream_state} | thinking={self.thinking_level} | state={state}"
        )
        self.query_one("#status", Static).update(
            Panel(Text(status_text), title="Proxy Session", border_style="cyan")
        )

    def _refresh_pane_titles(self) -> None:
        thinking_label = (
            f"Thinking · level={self.thinking_level.upper()} "
            f"(budget={THINKING_BUDGETS[self.thinking_level]})"
        )
        text_label = f"Text Stream · model={self.model}"
        self.query_one("#thinking_title", Static).update(thinking_label)
        self.query_one("#text_title", Static).update(text_label)

    def _reset_stream_panes(self) -> None:
        self._thinking_buffer = ""
        self._text_buffer = ""
        thinking_log = self.query_one("#thinking_log", RichLog)
        text_log = self.query_one("#text_log", RichLog)
        thinking_log.clear()
        text_log.clear()
        thinking_log.write(Text("No thinking output yet.", style="dim"))
        text_log.write(Text("No assistant text yet.", style="dim"))

    def _append_to_stream_log(
        self,
        log_id: str,
        previous: str,
        incoming: str,
        style: str = "",
    ) -> str:
        payload = str(incoming or "")
        if payload == previous:
            return previous

        if payload.startswith(previous):
            delta = payload[len(previous) :]
        else:
            delta = payload if not previous else f"\n{payload}"

        if not delta:
            return payload

        log = self.query_one(log_id, RichLog)
        if previous == "":
            # Drop placeholder on first real chunk.
            log.clear()
        text = Text(delta)
        if style:
            text.stylize(style)
        log.write(text, scroll_end=True)
        return payload

    def _log(self, message: str, style: str = "") -> None:
        ts = time.strftime("%H:%M:%S")
        text = Text(f"[{ts}] {message}")
        if style:
            text.stylize(style)
        self.query_one("#event_log", RichLog).write(text)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = (event.value or "").strip()
        event.input.value = ""
        if not value:
            return
        if value.startswith("/"):
            self._handle_command(value)
            return
        self._submit_prompt(value)

    def _submit_prompt(self, prompt: str) -> None:
        if self.busy:
            self._log("A request is already running.", style="bold yellow")
            return
        self.busy = True
        self._reset_stream_panes()
        self._refresh_status()
        self._log(f"user> {prompt}", style="cyan")

        snapshot = list(self.history)
        self._thread = Thread(
            target=self._worker_request,
            args=(prompt, snapshot),
            daemon=True,
        )
        self._thread.start()

    def _worker_request(self, prompt: str, history: Sequence[Turn]) -> None:
        def event_cb(kind: str, payload: str) -> None:
            self.call_from_thread(self._handle_proxy_event, kind, payload)

        try:
            answer = self.proxy_client.chat(
                prompt=prompt,
                history=history,
                model=self.model,
                stream=self.stream_enabled,
                thinking_level=self.thinking_level,
                on_event=event_cb,
            )
            self.call_from_thread(self._finish_request, prompt, answer, "")
        except Exception as exc:
            self.call_from_thread(self._finish_request, prompt, "", str(exc))

    def _handle_proxy_event(self, kind: str, payload: str) -> None:
        if kind == "thinking":
            self._thinking_buffer = self._append_to_stream_log(
                "#thinking_log", self._thinking_buffer, payload
            )
            return
        if kind == "text":
            self._text_buffer = self._append_to_stream_log(
                "#text_log", self._text_buffer, payload
            )
            return
        if kind == "meta":
            self._log(f"meta: {payload}", style="dim")
            return
        if kind == "event":
            self._log(payload, style="magenta")
            return
        if kind == "raw":
            self._log(f"stream: {payload}", style="dim")
            return
        self._log(f"{kind}: {payload}", style="dim")

    def _finish_request(self, prompt: str, answer: str, error: str) -> None:
        self.busy = False
        if error:
            self._log(f"error: {error}", style="bold red")
            self._refresh_status()
            return

        final = answer.strip()
        if final:
            self.history.extend([Turn("user", prompt), Turn("assistant", final)])
            self.history = self.history[-20:]
            self._text_buffer = self._append_to_stream_log(
                "#text_log", self._text_buffer, final
            )
            self._log("assistant> response completed", style="green")
        else:
            self._log("assistant> empty response", style="bold yellow")
        self._refresh_status()

    def _handle_command(self, raw_line: str) -> None:
        parts = raw_line.strip().split()
        cmd = parts[0].lower()

        if cmd in {"/quit", "/exit"}:
            self.action_quit()
            return

        if cmd == "/help":
            self._log("Commands:", style="bold")
            self._log("/model <model>                   set active model")
            self._log("/stream [on|off]                toggle/set streaming")
            self._log("/thinking <high|medium|low|none> set thinking level")
            self._log("/clear                           clear panes and logs")
            self._log("/quit                            exit")
            return

        if cmd == "/clear":
            self.action_clear_views()
            return

        if cmd == "/model":
            if len(parts) < 2:
                self._log("usage: /model <model>", style="bold yellow")
                return
            self.model = " ".join(parts[1:]).strip()
            self._log(f"model set to: {self.model}", style="green")
            self._refresh_pane_titles()
            self._refresh_status()
            return

        if cmd == "/stream":
            if len(parts) == 1:
                self.stream_enabled = not self.stream_enabled
            else:
                token = parts[1].lower()
                if token not in STREAM_TOGGLE_VALUES:
                    self._log("usage: /stream [on|off]", style="bold yellow")
                    return
                self.stream_enabled = STREAM_TOGGLE_VALUES[token]
            self._log(
                f"stream {'enabled' if self.stream_enabled else 'disabled'}",
                style="green",
            )
            self._refresh_status()
            return

        if cmd == "/thinking":
            if len(parts) < 2:
                self._log(
                    "usage: /thinking <high|medium|low|none>",
                    style="bold yellow",
                )
                return
            level = parts[1].lower()
            if level not in THINKING_LEVELS:
                self._log(
                    "invalid level. use: high|medium|low|none",
                    style="bold yellow",
                )
                return
            self.thinking_level = level
            self._log(
                f"thinking level set to: {self.thinking_level} "
                f"(budget={THINKING_BUDGETS[self.thinking_level]})",
                style="green",
            )
            self._refresh_pane_titles()
            self._refresh_status()
            return

        self._log(f"unknown command: {raw_line} (try /help)", style="bold yellow")

    def action_clear_views(self) -> None:
        self.query_one("#event_log", RichLog).clear()
        self._reset_stream_panes()
        self._log("cleared", style="dim")

    def action_toggle_stream(self) -> None:
        self.stream_enabled = not self.stream_enabled
        self._log(
            f"stream {'enabled' if self.stream_enabled else 'disabled'}",
            style="green",
        )
        self._refresh_status()

    def action_cycle_thinking(self) -> None:
        idx = THINKING_LEVELS.index(self.thinking_level)
        self.thinking_level = THINKING_LEVELS[(idx + 1) % len(THINKING_LEVELS)]
        self._log(
            f"thinking level set to: {self.thinking_level} "
            f"(budget={THINKING_BUDGETS[self.thinking_level]})",
            style="green",
        )
        self._refresh_pane_titles()
        self._refresh_status()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Textual TUI for Antigravity proxy")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8045",
        help="Proxy root base URL. Example: http://127.0.0.1:8045",
    )
    parser.add_argument(
        "--api-key",
        default="sk-15c5b9c69da44c88a53a7426b0433d91",
        help="Proxy API key",
    )
    parser.add_argument("--model", default="gemini-3-flash", help="Initial model")
    parser.add_argument(
        "--thinking",
        choices=THINKING_LEVELS,
        default="low",
        help="Initial thinking level",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming at startup (default: off)",
    )
    parser.add_argument("--timeout", type=float, default=90.0, help="Request timeout seconds")
    parser.add_argument("--max-tokens", type=int, default=1400, help="max_tokens")
    return parser


def main() -> None:
    args = _parser().parse_args()
    proxy_client = ProxySdkClient(
        base_url=args.base_url,
        api_key=args.api_key,
        timeout_sec=args.timeout,
        max_tokens=args.max_tokens,
    )
    app = ProxyTui(
        proxy_client=proxy_client,
        model=args.model,
        stream_enabled=bool(args.stream),
        thinking_level=args.thinking,
    )
    app.run()


if __name__ == "__main__":
    main()
