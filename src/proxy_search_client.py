import json
import logging
import re
import base64
import urllib.error
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.prompts import SYSTEM_PROMPT_SEARCH


logger = logging.getLogger(__name__)


class ProxySearchClientError(Exception):
    """Custom exception for Antigravity proxy search client errors."""


class ProxySearchClient:
    """
    OpenAI-compatible client for Antigravity local proxy search.

    This client is intentionally scoped to quick-answer web search:
    - Tries `-online` model suffix first.
    - Falls back to an explicit `web_search` tool marker.
    - Uses a fallback model if the primary path fails.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8045",
        api_key: str = "",
        primary_model: str = "gemini-3-flash",
        fallback_model: str = "gemini-2.5-flash",
        thinking_level: str = "high",
        timeout_sec: float = 75.0,
        max_tokens: int = 640,
    ):
        self.base_url = self._normalize_base_url(base_url)
        self.openai_base_url = self._to_openai_base_url(self.base_url)
        self.api_key = (api_key or "").strip()
        self.primary_model = (primary_model or "").strip() or "gemini-3-flash"
        self.fallback_model = (fallback_model or "").strip() or "gemini-2.5-flash"
        self.thinking_level = self._normalize_thinking_level(thinking_level)
        self.timeout_sec = max(5.0, float(timeout_sec))
        try:
            parsed_max_tokens = int(max_tokens)
        except Exception:
            parsed_max_tokens = 640
        self.max_tokens = max(128, parsed_max_tokens)
        self._sdk_client = None
        self._sdk_signature = ""
        self._sdk_missing_logged = False

    def update_config(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        thinking_level: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        if base_url is not None:
            self.base_url = self._normalize_base_url(base_url)
            self.openai_base_url = self._to_openai_base_url(self.base_url)
        if api_key is not None:
            self.api_key = str(api_key or "").strip()
        if primary_model is not None:
            normalized = str(primary_model or "").strip()
            if normalized:
                self.primary_model = normalized
        if fallback_model is not None:
            normalized = str(fallback_model or "").strip()
            if normalized:
                self.fallback_model = normalized
        if thinking_level is not None:
            self.thinking_level = self._normalize_thinking_level(thinking_level)
        if max_tokens is not None:
            try:
                parsed = int(max_tokens)
            except Exception:
                parsed = self.max_tokens
            self.max_tokens = max(128, parsed)
        self._sdk_client = None
        self._sdk_signature = ""

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        cleaned = (base_url or "").strip().rstrip("/")
        if not cleaned:
            return "http://127.0.0.1:8045"
        if "://" not in cleaned:
            return f"http://{cleaned}"
        return cleaned

    @staticmethod
    def _to_openai_base_url(base_url: str) -> str:
        cleaned = ProxySearchClient._normalize_base_url(base_url)
        if cleaned.endswith("/v1"):
            return cleaned
        return f"{cleaned}/v1"

    @staticmethod
    def _normalize_thinking_level(level: str) -> str:
        normalized = str(level or "").strip().lower()
        return normalized if normalized in {"high", "medium", "low", "none"} else "high"

    @staticmethod
    def _thinking_budget_from_level(level: str) -> int:
        mapping = {
            "none": 0,
            "low": 4096,
            "medium": 8192,
            "high": 24576,
        }
        return mapping.get(level, 24576)

    def _get_openai_client(self):
        key = self.api_key or "sk-antigravity"
        signature = f"{self.openai_base_url}|{key}|{self.timeout_sec}"
        if self._sdk_client is not None and signature == self._sdk_signature:
            return self._sdk_client

        try:
            from openai import OpenAI
        except Exception as exc:
            if not self._sdk_missing_logged:
                logger.warning(
                    "OpenAI SDK not installed; proxy client cannot use SDK transport: %s",
                    exc,
                )
                self._sdk_missing_logged = True
            self._sdk_client = None
            self._sdk_signature = ""
            return None

        self._sdk_client = OpenAI(
            base_url=self.openai_base_url,
            api_key=key,
            timeout=self.timeout_sec,
        )
        self._sdk_signature = signature
        self._sdk_missing_logged = False
        return self._sdk_client

    def _payload_to_sdk_params(
        self,
        payload: Dict[str, Any],
        stream: bool,
    ) -> Dict[str, Any]:
        known_keys = {
            "model",
            "messages",
            "temperature",
            "max_tokens",
            "top_p",
            "n",
            "stop",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "tools",
            "tool_choice",
            "response_format",
            "seed",
            "user",
            "stream",
        }
        params: Dict[str, Any] = {"stream": bool(stream)}
        extra_body: Dict[str, Any] = {}

        for key, value in payload.items():
            if key == "thinking":
                extra_body["thinking"] = value
                continue
            if key in known_keys and key != "stream":
                params[key] = value
                continue
            if key in known_keys:
                continue
            extra_body[key] = value

        if extra_body:
            params["extra_body"] = extra_body
        return params

    @staticmethod
    def _sdk_status_and_body(exc: Exception) -> Tuple[int, str, Optional[Dict[str, Any]]]:
        status = int(getattr(exc, "status_code", 0) or 0)
        response = getattr(exc, "response", None)
        raw = str(exc)
        if response is not None:
            try:
                text = response.text
                if isinstance(text, str) and text.strip():
                    raw = text
            except Exception:
                pass
            if status <= 0:
                try:
                    status = int(getattr(response, "status_code", 0) or 0)
                except Exception:
                    status = 0

        parsed = ProxySearchClient._safe_json_load(raw)
        lowered = raw.lower()
        if status <= 0 and ("timeout" in lowered or "timed out" in lowered):
            return 0, "timed out", parsed
        return status, raw, parsed

    def _urllib_json_request(
        self, method: str, path: str, payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}{path}"
        body: Optional[bytes] = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url=url,
            data=body,
            headers=headers,
            method=method.upper(),
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = self._safe_json_load(raw)
                return resp.status, dict(resp.headers.items()), parsed, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            parsed = self._safe_json_load(raw)
            return exc.code, dict(exc.headers.items()), parsed, raw
        except Exception as exc:
            return 0, {}, None, str(exc)

    def _json_request(
        self, method: str, path: str, payload: Optional[Dict[str, Any]] = None
    ) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
        if payload is None:
            return self._urllib_json_request(method, path, payload)

        if method.upper() != "POST" or path != "/v1/chat/completions":
            return self._urllib_json_request(method, path, payload)

        client = self._get_openai_client()
        if client is None:
            return 0, {}, None, "OpenAI SDK is required: pip install openai"

        params = self._payload_to_sdk_params(payload, stream=False)
        try:
            response = client.chat.completions.create(**params)
            payload_json = response.model_dump(exclude_none=True)
            raw = json.dumps(payload_json, ensure_ascii=False)
            headers: Dict[str, str] = {}
            mapped_model = payload_json.get("model")
            if isinstance(mapped_model, str) and mapped_model:
                headers["X-Mapped-Model"] = mapped_model
            return 200, headers, payload_json, raw
        except Exception as exc:
            status, raw, parsed = self._sdk_status_and_body(exc)
            return status, {}, parsed, raw

    @staticmethod
    def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(text)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _emit_step(step_callback: Optional[Callable[[str], None]], text: str) -> None:
        if step_callback is None:
            return
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return
        try:
            step_callback(cleaned)
        except Exception:
            logger.debug("Proxy step callback failed", exc_info=True)

    @staticmethod
    def _emit_stream_text(
        stream_callback: Optional[Callable[[str], None]],
        text: str,
    ) -> None:
        if stream_callback is None:
            return
        if not text:
            return
        try:
            stream_callback(text)
        except Exception:
            logger.debug("Proxy stream callback failed", exc_info=True)

    @staticmethod
    def _consume_reasoning_headers(
        buffer: str,
        last_header: str,
        emit_step: Callable[[str], None],
    ) -> Tuple[str, str]:
        pending = str(buffer or "")
        newest = str(last_header or "")
        while True:
            start = pending.find("**")
            if start < 0:
                # Keep a tiny tail so split markers across chunk boundaries survive.
                return pending[-1:] if pending.endswith("*") else "", newest
            if start > 0:
                pending = pending[start:]

            end = pending.find("**", 2)
            if end < 0:
                return pending, newest

            raw = pending[2:end]
            pending = pending[end + 2 :]

            if "\n" in raw:
                continue
            cleaned = " ".join(raw.split()).strip()
            if not cleaned:
                continue
            if cleaned == newest:
                continue
            newest = cleaned
            emit_step(cleaned)

    @staticmethod
    def _contains_stream_search_marker(text: str) -> bool:
        lowered = (text or "").lower()
        return (
            "web_search" in lowered
            or "grounding-api-redirect" in lowered
            or "vertexaisearch.cloud.google.com" in lowered
            or "来源引文" in text
            or "已为您搜索" in text
            or ("**🔍" in text and "**🌐" in text)
        )

    @staticmethod
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

    def _stream_chat_completion(
        self,
        payload: Dict[str, Any],
        step_callback: Optional[Callable[[str], None]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[int, Dict[str, str], Optional[Dict[str, Any]], str]:
        client = self._get_openai_client()
        if client is None:
            return 0, {}, None, "OpenAI SDK is required: pip install openai"

        raw_preview: List[str] = []
        text_content = ""
        finish_reason = ""
        last_step = ""
        last_stream_text = ""
        reasoning_header_buffer = ""
        last_reasoning_header = ""
        response_headers: Dict[str, str] = {}

        def emit_step(text: str) -> None:
            nonlocal last_step
            cleaned = " ".join(str(text or "").split()).strip()
            if not cleaned or cleaned == last_step:
                return
            last_step = cleaned
            self._emit_step(step_callback, cleaned)

        def _extract_content_delta(delta: Dict[str, Any]) -> str:
            content = delta.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                chunks: List[str] = []
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        chunks.append(text)
                return "".join(chunks)
            return ""

        params = self._payload_to_sdk_params(payload, stream=True)
        try:
            stream = client.chat.completions.create(**params)
            emit_step("Awaiting model stream")

            for chunk in stream:
                chunk_dict = chunk.model_dump(exclude_none=True)
                if len(raw_preview) < 30:
                    raw_preview.append(json.dumps(chunk_dict, ensure_ascii=False)[:700])

                mapped_model = chunk_dict.get("model")
                if isinstance(mapped_model, str) and mapped_model:
                    response_headers["X-Mapped-Model"] = mapped_model

                choices = chunk_dict.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                delta = choice0.get("delta") if isinstance(choice0, dict) else {}
                if not isinstance(delta, dict):
                    continue

                reasoning = delta.get("reasoning_content")
                if isinstance(reasoning, str) and reasoning:
                    reasoning_header_buffer += reasoning
                    (
                        reasoning_header_buffer,
                        last_reasoning_header,
                    ) = self._consume_reasoning_headers(
                        reasoning_header_buffer,
                        last_reasoning_header,
                        emit_step,
                    )

                tool_names = self._extract_tool_names(delta)
                if tool_names:
                    first_name = tool_names[0].lower()
                    if "search" in first_name:
                        emit_step("Searching the web")
                    else:
                        emit_step(f"Using tool: {tool_names[0]}")

                content_delta = _extract_content_delta(delta)
                if content_delta:
                    text_content = self._merge_text_fragments(text_content, content_delta)
                    if text_content != last_stream_text:
                        last_stream_text = text_content
                        self._emit_stream_text(stream_callback, text_content)
                    if self._contains_stream_search_marker(content_delta):
                        emit_step("Using web results")
                    else:
                        emit_step("Writing answer")

                found_finish = choice0.get("finish_reason")
                if isinstance(found_finish, str) and found_finish:
                    finish_reason = found_finish
                    emit_step("Finalizing answer")

            if text_content.strip():
                result_payload: Dict[str, Any] = {
                    "choices": [
                        {
                            "message": {"content": text_content},
                            "finish_reason": finish_reason or "stop",
                        }
                    ]
                }
                return 200, response_headers, result_payload, "\n".join(raw_preview)

            return 200, response_headers, None, "\n".join(raw_preview)
        except Exception as exc:
            status, raw, parsed = self._sdk_status_and_body(exc)
            return status, {}, parsed, raw

    @staticmethod
    def _extract_content(payload: Optional[Dict[str, Any]]) -> str:
        if not isinstance(payload, dict):
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

    @staticmethod
    def _extract_finish_reason(payload: Optional[Dict[str, Any]]) -> str:
        if not isinstance(payload, dict):
            return ""
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        finish_reason = first.get("finish_reason", "")
        return finish_reason if isinstance(finish_reason, str) else str(finish_reason)

    @staticmethod
    def _merge_text_fragments(existing: str, fragment: str) -> str:
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

    @staticmethod
    def _build_continuation_payload(base_payload: Dict[str, Any], assistant_text: str) -> Dict[str, Any]:
        payload = dict(base_payload)
        messages = list(base_payload.get("messages") or [])
        messages.append({"role": "assistant", "content": assistant_text})
        messages.append(
            {
                "role": "user",
                "content": "Continue exactly from where you stopped. Do not repeat prior text.",
            }
        )
        payload["messages"] = messages
        payload["stream"] = False
        return payload

    def _collect_continued_answer(
        self,
        base_payload: Dict[str, Any],
        initial_raw_content: str,
        initial_finish_reason: str,
        label: str,
        model_name: str,
        max_rounds: int = 4,
    ) -> Tuple[str, str, bool]:
        combined_raw = str(initial_raw_content or "").strip()
        combined_cleaned = self._strip_proxy_grounding(combined_raw)
        finish_reason = str(initial_finish_reason or "").strip().lower()
        if finish_reason != "length":
            return combined_raw, combined_cleaned, False

        logger.warning(
            "Proxy response truncated on attempt '%s' model='%s'; requesting continuation.",
            label,
            model_name,
        )
        for _ in range(max(1, int(max_rounds))):
            followup_payload = self._build_continuation_payload(base_payload, combined_raw)
            status, _, response_json, raw = self._json_request(
                "POST", "/v1/chat/completions", followup_payload
            )
            if status != 200:
                logger.warning(
                    "Continuation request failed on attempt '%s' model='%s' status=%s: %s",
                    label,
                    model_name,
                    status,
                    raw[:160],
                )
                break

            next_raw = self._extract_content(response_json).strip()
            if not next_raw:
                break
            if next_raw.upper() == "[DONE]":
                break

            combined_raw = self._merge_text_fragments(combined_raw, next_raw)
            next_cleaned = self._strip_proxy_grounding(next_raw)
            if next_cleaned:
                combined_cleaned = self._merge_text_fragments(combined_cleaned, next_cleaned)

            finish_reason = self._extract_finish_reason(response_json).strip().lower()
            if finish_reason != "length":
                break

        return combined_raw, combined_cleaned, finish_reason == "length"

    @staticmethod
    def _strip_proxy_grounding(answer: str) -> str:
        trimmed = answer
        markers = (
            "\n\n---\n**🔍",
            "\n\n---\n**🌐",
            "\n\n---\n**Search",
            "\n\n---\n**Sources",
        )
        for marker in markers:
            idx = trimmed.find(marker)
            if idx != -1:
                trimmed = trimmed[:idx]
                break

        # Strip leaked tool-trace suffixes that can appear in truncated responses.
        # Examples seen in the wild: "search{queries:[...]" or "web_search{query:[...]".
        tool_trace = re.search(
            r"(?:web_)?search\s*\{\s*quer(?:y|ies)\s*:\s*\[.*$",
            trimmed,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if tool_trace is not None:
            cut_idx = tool_trace.start()
            # Some traces are prefixed with a stray CJK char (e.g. "旁search{...}").
            if cut_idx > 0 and "\u4e00" <= trimmed[cut_idx - 1] <= "\u9fff":
                cut_idx -= 1
            trimmed = trimmed[:cut_idx]

        # Remove occasional transient tags leaked by proxy internals.
        trimmed = re.sub(
            r"<[^>\n]{0,24}tr\d+[^>\n]{0,24}>",
            "",
            trimmed,
            flags=re.IGNORECASE,
        )

        # Remove inline citation markers often emitted before the citation block.
        trimmed = re.sub(
            r"\s*\[(?:\d+(?:\.\d+)?(?:\s*,\s*\d+(?:\.\d+)?)*)\]",
            "",
            trimmed,
        )
        trimmed = re.sub(r"[ \t]{2,}", " ", trimmed)
        return trimmed.strip()

    def _build_payload(
        self,
        model: str,
        query: str,
        system_prompt: str,
        use_online_suffix: bool,
        include_search_tool: bool,
        image_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        chosen_model = model.strip()
        if use_online_suffix and not chosen_model.endswith("-online"):
            chosen_model = f"{chosen_model}-online"

        user_content: Any = query
        if image_bytes:
            encoded = base64.b64encode(image_bytes).decode("ascii")
            user_content = [
                {"type": "text", "text": query},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                },
            ]

        messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": user_content})

        payload: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": False,
        }

        thinking_budget = self._thinking_budget_from_level(self.thinking_level)
        payload["thinking"] = {
            "type": "enabled" if thinking_budget > 0 else "disabled",
            "budget_tokens": thinking_budget,
        }

        if include_search_tool:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for current information.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                            },
                        },
                    },
                }
            ]

        return payload

    @staticmethod
    def _has_grounding_markers(text: str) -> bool:
        lowered = (text or "").lower()
        return (
            "已为您搜索" in text
            or "来源引文" in text
            or "grounding-api-redirect" in lowered
            or "vertexaisearch.cloud.google.com" in lowered
            or ("**🔍" in text and "**🌐" in text)
        )

    @staticmethod
    def _is_time_sensitive_query(query: str) -> bool:
        lowered = (query or "").lower()
        keywords = (
            "weather",
            "temperature",
            "humidity",
            "forecast",
            "rain",
            "precip",
            "stock",
            "price",
            "news",
            "latest",
            "current",
            "today",
            "now",
            "atm",
            "right now",
        )
        return any(token in lowered for token in keywords)

    @staticmethod
    def _is_weather_query(query: str) -> bool:
        lowered = (query or "").lower()
        return any(
            token in lowered
            for token in ("weather", "temperature", "humidity", "forecast", "rain", "precip")
        )

    @staticmethod
    def _query_requests_humidity(query: str) -> bool:
        lowered = (query or "").lower()
        return "humidity" in lowered or "humid" in lowered

    @staticmethod
    def _query_requests_precip(query: str) -> bool:
        lowered = (query or "").lower()
        return any(token in lowered for token in ("rain", "precip", "chance of rain"))

    @staticmethod
    def _looks_like_weather_answer(
        answer: str,
        require_humidity: bool,
        require_precip: bool,
    ) -> bool:
        text = answer or ""
        has_temp = bool(
            re.search(r"-?\d+(?:\.\d+)?\s*°\s*[cf]\b", text, flags=re.IGNORECASE)
            or re.search(r"-?\d+(?:\.\d+)?\s*(?:celsius|fahrenheit)\b", text, flags=re.IGNORECASE)
            or re.search(r"temperature[^0-9-]{0,20}-?\d+(?:\.\d+)?", text, flags=re.IGNORECASE)
        )
        has_humidity = bool(
            re.search(r"humidity[^0-9]{0,24}\d{1,3}(?:\.\d+)?\s*%", text, flags=re.IGNORECASE)
            or re.search(r"\d{1,3}(?:\.\d+)?\s*%\s*humidity", text, flags=re.IGNORECASE)
        )
        has_precip = bool(
            re.search(r"(rain|precip)[^0-9]{0,24}\d{1,3}(?:\.\d+)?\s*%", text, flags=re.IGNORECASE)
            or re.search(
                r"\d{1,3}(?:\.\d+)?\s*%\s*(chance of rain|rain|precip)",
                text,
                flags=re.IGNORECASE,
            )
        )

        if not has_temp:
            return False
        if require_humidity and not has_humidity:
            return False
        if require_precip and not has_precip:
            return False
        return True

    @staticmethod
    def _should_fallback_to_json_after_stream_failure(status: int, raw: str) -> bool:
        if int(status or 0) == 200:
            return False
        lowered = str(raw or "").lower()
        if int(status or 0) == 0 and ("timed out" in lowered or "timeout" in lowered):
            return False
        return True

    def run_search(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
        step_callback: Optional[Callable[[str], None]] = None,
        stream_callback: Optional[Callable[[str], None]] = None,
    ) -> str:
        prompt = (system_prompt or SYSTEM_PROMPT_SEARCH).strip()
        clean_query = (query or "").strip()

        if not clean_query:
            return ""

        attempts = [
            (
                self.primary_model,
                self._build_payload(
                    self.primary_model,
                    clean_query,
                    prompt,
                    use_online_suffix=True,
                    include_search_tool=False,
                    image_bytes=image_bytes,
                ),
                "primary-online",
            ),
            (
                self.primary_model,
                self._build_payload(
                    self.primary_model,
                    clean_query,
                    prompt,
                    use_online_suffix=False,
                    include_search_tool=True,
                    image_bytes=image_bytes,
                ),
                "primary-tool",
            ),
        ]

        if self.fallback_model and self.fallback_model != self.primary_model:
            attempts.extend(
                [
                    (
                        self.fallback_model,
                        self._build_payload(
                            self.fallback_model,
                            clean_query,
                            prompt,
                            use_online_suffix=True,
                            include_search_tool=False,
                            image_bytes=image_bytes,
                        ),
                        "fallback-online",
                    ),
                    (
                        self.fallback_model,
                        self._build_payload(
                            self.fallback_model,
                            clean_query,
                            prompt,
                            use_online_suffix=False,
                            include_search_tool=True,
                            image_bytes=image_bytes,
                        ),
                        "fallback-tool",
                    ),
                ]
            )

        errors = []
        best_partial = ""
        needs_grounding = self._is_time_sensitive_query(clean_query)
        weather_query = self._is_weather_query(clean_query)
        require_humidity = self._query_requests_humidity(clean_query)
        require_precip = self._query_requests_precip(clean_query)

        for model_name, payload, label in attempts:
            self._emit_step(step_callback, "Sending API request")
            if step_callback is not None:
                streaming_payload = dict(payload)
                streaming_payload["stream"] = True
                if stream_callback is not None:
                    status, response_headers, response_json, raw = self._stream_chat_completion(
                        streaming_payload,
                        step_callback=step_callback,
                        stream_callback=stream_callback,
                    )
                else:
                    status, response_headers, response_json, raw = self._stream_chat_completion(
                        streaming_payload,
                        step_callback=step_callback,
                    )
                if status != 200 and self._should_fallback_to_json_after_stream_failure(status, raw):
                    status, response_headers, response_json, raw = self._json_request(
                        "POST", "/v1/chat/completions", payload
                    )
            else:
                status, response_headers, response_json, raw = self._json_request(
                    "POST", "/v1/chat/completions", payload
                )
            mapped_model = response_headers.get("X-Mapped-Model") or response_headers.get(
                "x-mapped-model", ""
            )
            logger.info(
                "Proxy search attempt '%s' model='%s' mapped='%s' status=%s",
                label,
                model_name,
                mapped_model,
                status,
            )

            if status != 200:
                errors.append(f"{label}:{status}:{raw[:180]}")
                continue

            raw_content = self._extract_content(response_json)
            if raw_content.strip():
                finish_reason = self._extract_finish_reason(response_json).strip().lower()
                full_raw, cleaned, is_still_truncated = self._collect_continued_answer(
                    payload,
                    raw_content,
                    finish_reason,
                    label=label,
                    model_name=model_name,
                )
                has_grounding = self._has_grounding_markers(full_raw)

                if needs_grounding and not has_grounding:
                    errors.append(f"{label}:200:ungrounded")
                    logger.warning(
                        "Rejecting ungrounded time-sensitive response on attempt '%s' model='%s'",
                        label,
                        model_name,
                    )
                    continue

                if weather_query and not self._looks_like_weather_answer(
                    cleaned,
                    require_humidity=require_humidity,
                    require_precip=require_precip,
                ):
                    errors.append(f"{label}:200:incomplete-weather")
                    logger.warning(
                        "Rejecting incomplete weather response on attempt '%s' model='%s': %s",
                        label,
                        model_name,
                        cleaned[:160],
                    )
                    continue

                if cleaned:
                    if is_still_truncated:
                        errors.append(f"{label}:200:truncated-length")
                        if not best_partial:
                            best_partial = cleaned
                        logger.warning(
                            "Rejecting still-truncated response on attempt '%s' model='%s'",
                            label,
                            model_name,
                        )
                        continue
                    self._emit_step(step_callback, "Finalizing answer")
                    return cleaned

            errors.append(f"{label}:200:empty-content")

        if best_partial:
            logger.warning("Returning partial proxy answer after all attempts remained truncated.")
            return best_partial

        raise ProxySearchClientError(
            "Proxy search failed after all attempts: " + " | ".join(errors)
        )
