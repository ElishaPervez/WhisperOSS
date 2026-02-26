import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "proxy_streaming_probe.py"
spec = importlib.util.spec_from_file_location("proxy_streaming_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(probe)


def test_summarize_detects_reasoning_and_generation_steps():
    events = [
        {
            "kind": "data",
            "event": "message",
            "data": '{"choices":[{"delta":{"reasoning_content":"Let me think quickly."},"finish_reason":null}]}' ,
            "json": {
                "choices": [
                    {
                        "delta": {"reasoning_content": "Let me think quickly."},
                        "finish_reason": None,
                    }
                ]
            },
            "t_ms": 12,
        },
        {
            "kind": "data",
            "event": "message",
            "data": '{"choices":[{"delta":{"content":"Run ipconfig /flushdns"},"finish_reason":null}]}' ,
            "json": {
                "choices": [
                    {
                        "delta": {"content": "Run ipconfig /flushdns"},
                        "finish_reason": None,
                    }
                ]
            },
            "t_ms": 38,
        },
        {"kind": "data", "event": "message", "data": "[DONE]", "t_ms": 55},
    ]

    summary = probe._summarize_events(events)

    assert summary["has_reasoning_content"] is True
    steps = [item["step"] for item in summary["step_timeline"]]
    assert "thinking" in steps
    assert "generating_answer" in steps
    assert steps[-1] == "completed"


def test_summarize_detects_tool_call_name():
    events = [
        {
            "kind": "data",
            "event": "message",
            "data": '{"choices":[{"delta":{"tool_calls":[{"function":{"name":"web_search","arguments":"{}"}}]},"finish_reason":null}]}' ,
            "json": {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "web_search",
                                        "arguments": "{}",
                                    }
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            "t_ms": 24,
        }
    ]

    summary = probe._summarize_events(events)

    assert summary["has_tool_calls"] is True
    assert "web_search" in summary["tool_names"]
    assert summary["step_timeline"][0]["step"] == "calling_tool"


def test_summarize_detects_codex_event_flow():
    events = [
        {
            "kind": "data",
            "event": "message",
            "data": '{"type":"response.created","response":{"id":"resp-1"}}',
            "json": {"type": "response.created", "response": {"id": "resp-1"}},
            "t_ms": 1,
        },
        {
            "kind": "data",
            "event": "message",
            "data": '{"type":"response.output_text.delta","delta":"Hello"}',
            "json": {"type": "response.output_text.delta", "delta": "Hello"},
            "t_ms": 10,
        },
        {
            "kind": "data",
            "event": "message",
            "data": '{"type":"response.completed","response":{"status":"completed"}}',
            "json": {
                "type": "response.completed",
                "response": {"status": "completed"},
            },
            "t_ms": 19,
        },
    ]

    summary = probe._summarize_events(events)

    steps = [item["step"] for item in summary["step_timeline"]]
    assert steps[0] == "starting"
    assert "generating_answer" in steps
    assert steps[-1] == "completed"
    assert summary["event_types"]["response.created"] == 1
    assert summary["event_types"]["response.output_text.delta"] == 1
    assert summary["event_types"]["response.completed"] == 1
