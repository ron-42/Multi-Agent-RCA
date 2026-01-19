"""Logger - Logs all tool calls to message_history.json with tracing support"""

import os
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

MESSAGE_HISTORY_PATH = "memory/message_history.json"

# Global trace context
_current_trace_id: Optional[str] = None
_current_span_id: Optional[str] = None
_span_start_times: dict = {}


def generate_id() -> str:
    """Generate a short unique ID for traces/spans."""
    return uuid.uuid4().hex[:12]


def start_trace() -> str:
    """Start a new trace and return the trace ID."""
    global _current_trace_id
    _current_trace_id = generate_id()
    return _current_trace_id


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID."""
    return _current_trace_id


def _append_to_history(entry: dict):
    """Append an entry to message history."""
    os.makedirs(os.path.dirname(MESSAGE_HISTORY_PATH), exist_ok=True)

    history = []
    if os.path.exists(MESSAGE_HISTORY_PATH):
        try:
            with open(MESSAGE_HISTORY_PATH, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            history = []

    history.append(entry)

    with open(MESSAGE_HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def log_tool_call(tool_name: str, method: str, data: dict, span_id: Optional[str] = None):
    """Log a tool call to message_history.json.

    Args:
        tool_name: Name of the tool (FileReader, FileWriter, CodeSearch)
        method: Method being called
        data: Input/output data to log
        span_id: Optional span ID to associate this tool call with
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "tool_call",
        "tool": tool_name,
        "method": method,
        "data": data,
        "trace_id": _current_trace_id,
        "span_id": span_id or _current_span_id
    }
    _append_to_history(entry)


def log_agent_message(agent_name: str, event: str, data: dict):
    """Log an agent event to message_history.json.

    Args:
        agent_name: Name of the agent
        event: Event type (start, complete, etc.)
        data: Event data to log
    """
    global _current_span_id

    span_id = None
    duration_ms = None

    if event == "start":
        span_id = generate_id()
        _current_span_id = span_id
        _span_start_times[span_id] = datetime.now(timezone.utc)
    elif event == "complete" and _current_span_id:
        span_id = _current_span_id
        if span_id in _span_start_times:
            start_time = _span_start_times[span_id]
            duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            del _span_start_times[span_id]
    else:
        span_id = _current_span_id

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "agent_event",
        "agent": agent_name,
        "event": event,
        "data": data,
        "trace_id": _current_trace_id,
        "span_id": span_id
    }

    if duration_ms is not None:
        entry["duration_ms"] = duration_ms

    _append_to_history(entry)


def log_llm_call(agent_name: str, prompt_tokens: Optional[int] = None,
                 completion_tokens: Optional[int] = None,
                 model: str = "gpt-4o", latency_ms: Optional[int] = None):
    """Log an LLM API call with token counts and latency.

    Args:
        agent_name: Name of the agent making the call
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model name used
        latency_ms: API call latency in milliseconds
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "llm_call",
        "agent": agent_name,
        "model": model,
        "trace_id": _current_trace_id,
        "span_id": _current_span_id,
        "tokens": {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": (prompt_tokens or 0) + (completion_tokens or 0) if prompt_tokens or completion_tokens else None
        },
        "latency_ms": latency_ms
    }
    _append_to_history(entry)
