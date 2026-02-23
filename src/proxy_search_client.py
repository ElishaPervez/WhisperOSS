import json
import logging
import re
import base64
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

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
        timeout_sec: float = 25.0,
        max_tokens: int = 640,
    ):
        self.base_url = self._normalize_base_url(base_url)
        self.api_key = (api_key or "").strip()
        self.primary_model = (primary_model or "").strip() or "gemini-3-flash"
        self.fallback_model = (fallback_model or "").strip() or "gemini-2.5-flash"
        self.timeout_sec = max(5.0, float(timeout_sec))
        try:
            parsed_max_tokens = int(max_tokens)
        except Exception:
            parsed_max_tokens = 640
        self.max_tokens = max(128, parsed_max_tokens)

    def update_config(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        if base_url is not None:
            self.base_url = self._normalize_base_url(base_url)
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
        if max_tokens is not None:
            try:
                parsed = int(max_tokens)
            except Exception:
                parsed = self.max_tokens
            self.max_tokens = max(128, parsed)

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        cleaned = (base_url or "").strip().rstrip("/")
        if not cleaned:
            return "http://127.0.0.1:8045"
        if "://" not in cleaned:
            return f"http://{cleaned}"
        return cleaned

    def _json_request(
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

    @staticmethod
    def _safe_json_load(text: str) -> Optional[Dict[str, Any]]:
        try:
            payload = json.loads(text)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

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

        payload: Dict[str, Any] = {
            "model": chosen_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": False,
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

    def run_search(
        self,
        query: str,
        system_prompt: Optional[str] = None,
        image_bytes: Optional[bytes] = None,
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
                    return cleaned

            errors.append(f"{label}:200:empty-content")

        if best_partial:
            logger.warning("Returning partial proxy answer after all attempts remained truncated.")
            return best_partial

        raise ProxySearchClientError(
            "Proxy search failed after all attempts: " + " | ".join(errors)
        )
