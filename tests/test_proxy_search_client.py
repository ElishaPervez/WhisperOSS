import pytest

from src.proxy_search_client import ProxySearchClient, ProxySearchClientError


def test_run_search_prefers_online_suffix_and_strips_grounding():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3.1-pro-high",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        return (
            200,
            {"X-Mapped-Model": "gemini-3.1-pro-high-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Paris\n\n---\n**🔍 已为您搜索：** capital of france",
                        }
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("capital of france")
    assert result == "Paris"
    assert calls[0]["model"] == "gemini-3.1-pro-high-online"
    assert "tools" not in calls[0]


def test_run_search_falls_back_to_tool_marker_on_primary_failure():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3.1-pro-high",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) == 1:
            return 429, {}, None, "quota exhausted"
        return (
            200,
            {"X-Mapped-Model": "gemini-3.1-pro-high"},
            {"choices": [{"message": {"content": "Paris"}}]},
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("capital of france")
    assert result == "Paris"
    assert calls[0]["model"] == "gemini-3.1-pro-high-online"
    assert calls[1]["model"] == "gemini-3.1-pro-high"
    assert "tools" in calls[1]


def test_run_search_uses_fallback_model_if_primary_attempts_fail():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3.1-pro-high",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) < 3:
            return 503, {}, None, "all accounts exhausted"
        return (
            200,
            {"X-Mapped-Model": "gemini-2.5-flash-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Tokyo: 15°C\n\n---\n**🔍 已为您搜索：** weather in tokyo",
                        }
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("weather in tokyo")
    assert result == "Tokyo: 15°C"
    assert calls[2]["model"] == "gemini-2.5-flash-online"


def test_run_search_raises_after_all_attempts():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3.1-pro-high",
        fallback_model="gemini-2.5-flash",
    )

    def fake_json_request(method, path, payload):
        return 503, {}, None, "no accounts available with quota"

    client._json_request = fake_json_request

    with pytest.raises(ProxySearchClientError):
        client.run_search("weather in tokyo")


def test_run_search_retries_if_time_sensitive_answer_is_ungrounded():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) == 1:
            return (
                200,
                {"X-Mapped-Model": "gemini-3-flash-online"},
                {"choices": [{"message": {"content": "Karachi: 23°C, 73% humidity"}}]},
                "",
            )
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Karachi: 23°C, 73% humidity\n\n---\n**🔍 已为您搜索：** current weather",
                        }
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request
    result = client.run_search("weather in karachi now with humidity")
    assert result == "Karachi: 23°C, 73% humidity"
    assert len(calls) == 2
    assert "tools" in calls[1]


def test_run_search_retries_if_weather_fields_are_missing():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) == 1:
            return (
                200,
                {"X-Mapped-Model": "gemini-3-flash-online"},
                {
                    "choices": [
                        {
                            "message": {
                                "content": "Karachi: 25°C\n\n---\n**🔍 已为您搜索：** current weather",
                            }
                        }
                    ]
                },
                "",
            )
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Karachi: 25°C, 57% humidity\n\n---\n**🔍 已为您搜索：** current weather humidity",
                        }
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request
    result = client.run_search("weather in karachi now in celsius and humidity")
    assert result == "Karachi: 25°C, 57% humidity"
    assert len(calls) == 2


def test_run_search_builds_multimodal_payload_when_image_is_provided():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {"choices": [{"message": {"content": "Looks like a settings icon."}}]},
            "",
        )

    client._json_request = fake_json_request
    result = client.run_search("what icon is this", image_bytes=b"\x89PNG\r\n\x1a\nfake")
    assert result == "Looks like a settings icon."
    content = calls[0]["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_run_search_includes_thinking_budget_from_level():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
        thinking_level="low",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {"choices": [{"message": {"content": "Looks good."}}]},
            "",
        )

    client._json_request = fake_json_request
    result = client.run_search("quick check")

    assert result == "Looks good."
    assert calls
    assert calls[0]["thinking"]["type"] == "enabled"
    assert calls[0]["thinking"]["budget_tokens"] == 4096


def test_run_search_auto_continues_when_finish_reason_is_length():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) == 1:
            return (
                200,
                {"X-Mapped-Model": "gemini-3-flash-online"},
                {
                    "choices": [
                        {
                            "message": {
                                "content": "The character appears to be Daniel from the series",
                            },
                            "finish_reason": "length",
                        }
                    ]
                },
                "",
            )

        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": " based on the hairstyle and uniform details.",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request
    result = client.run_search("who is this character")
    assert result == (
        "The character appears to be Daniel from the series"
        " based on the hairstyle and uniform details."
    )
    assert len(calls) == 2
    assert calls[1]["messages"][2]["role"] == "assistant"
    assert "Continue exactly from where you stopped" in calls[1]["messages"][3]["content"]


def test_strip_proxy_grounding_removes_leaked_search_trace_suffix():
    raw = (
        "ZOTAC and PNY both target similar price tiers, but PNY is quieter."
        "旁search{queries:[<tr146>ZOTAC twin edge vs PNY RTX build quality]}"
    )

    cleaned = ProxySearchClient._strip_proxy_grounding(raw)

    assert cleaned == "ZOTAC and PNY both target similar price tiers, but PNY is quieter."


def test_run_search_strips_leaked_search_trace_from_answer():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )

    def fake_json_request(method, path, payload):
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                "PNY generally has lower noise levels than ZOTAC."
                                " search{queries:[zotac vs pny noise levels]}"
                            )
                        }
                    }
                ]
            },
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("zotac twin edge vs pny noise")
    assert result == "PNY generally has lower noise levels than ZOTAC."


def test_run_search_tries_next_attempt_when_continuation_remains_truncated():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        if len(calls) == 1:
            return (
                200,
                {"X-Mapped-Model": "gemini-3-flash-online"},
                {
                    "choices": [
                        {
                            "message": {"content": "PNY is usually quieter than ZOTAC"},
                            "finish_reason": "length",
                        }
                    ]
                },
                "",
            )
        if len(calls) == 2:
            # Continuation request returns no useful content and remains truncated.
            return (
                200,
                {"X-Mapped-Model": "gemini-3-flash-online"},
                {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]},
                "",
            )
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash"},
            {"choices": [{"message": {"content": "PNY is usually quieter than ZOTAC in similar SKUs."}}]},
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("zotac twin edge vs pny rtx noise")
    assert result == "PNY is usually quieter than ZOTAC in similar SKUs."
    assert len(calls) == 3
    assert calls[2]["model"] == "gemini-3-flash"
    assert "tools" in calls[2]


def test_run_search_is_stateless_payload():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    calls = []

    def fake_json_request(method, path, payload):
        calls.append(payload)
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {"choices": [{"message": {"content": "Use the confirmed fix from thread X."}}]},
            "",
        )

    client._json_request = fake_json_request

    result = client.run_search("my new issue")

    assert result == "Use the confirmed fix from thread X."
    assert calls
    messages = calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert len(messages) == 2
    assert messages[1] == {"role": "user", "content": "my new issue"}


def test_run_search_uses_streaming_path_when_step_callback_is_present():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    steps = []

    def fake_stream(payload, step_callback=None):
        assert payload["stream"] is True
        if step_callback is not None:
            step_callback("Sending API request")
            step_callback("Thinking")
            step_callback("Searching the web")
            step_callback("Using web results")
            step_callback("Writing answer")
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Use this exact fix from the thread.",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
            "",
        )

    client._stream_chat_completion = fake_stream

    result = client.run_search("specific issue", step_callback=steps.append)

    assert result == "Use this exact fix from the thread."
    assert "Sending API request" in steps
    assert "Searching the web" in steps
    assert "Using web results" in steps
    assert "Thinking" in steps
    assert "Finalizing answer" in steps


def test_run_search_falls_back_to_json_when_stream_request_fails():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    json_calls = []

    def fake_stream(payload, step_callback=None):
        return 503, {}, None, "stream unavailable"

    def fake_json_request(method, path, payload):
        json_calls.append(payload)
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {"choices": [{"message": {"content": "Recovered via non-stream request."}}]},
            "",
        )

    client._stream_chat_completion = fake_stream
    client._json_request = fake_json_request

    result = client.run_search("specific issue", step_callback=lambda _: None)

    assert result == "Recovered via non-stream request."
    assert len(json_calls) == 1


def test_run_search_does_not_emit_searching_web_without_search_signals():
    client = ProxySearchClient(
        base_url="http://127.0.0.1:8045",
        primary_model="gemini-3-flash",
        fallback_model="gemini-2.5-flash",
    )
    steps = []

    def fake_stream(payload, step_callback=None):
        if step_callback is not None:
            step_callback("Thinking")
            step_callback("Writing answer")
        return (
            200,
            {"X-Mapped-Model": "gemini-3-flash-online"},
            {
                "choices": [
                    {
                        "message": {
                            "content": "Boil or fry an egg.",
                        },
                        "finish_reason": "stop",
                    }
                ]
            },
            "",
        )

    client._stream_chat_completion = fake_stream

    result = client.run_search("how to make an egg", step_callback=steps.append)

    assert result == "Boil or fry an egg."
    assert "Sending API request" in steps
    assert "Searching the web" not in steps
