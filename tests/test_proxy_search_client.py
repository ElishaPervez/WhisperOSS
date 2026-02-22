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
