"""
Tests for AgentTraceRecorder: step creation, tool decoration, and file persistence.
"""

import os
import tempfile
from agenttrace.recorder import AgentTraceRecorder
from agenttrace.models import ToolStatus


def test_recorder_step_and_tool_tracking():
    rec = AgentTraceRecorder(task_prompt="Audit API endpoints", agent_model="test-agent")
    rec.start_step(role="assistant", thought="Checking status", content="All looks good.")
    tc = rec.record_tool_call(name="ping", arguments={"host": "127.0.0.1"})
    rec.record_tool_result(call_id=tc.call_id, name="ping", status=ToolStatus.SUCCESS, output="64 bytes")

    trace = rec.complete()
    assert len(trace.steps) == 1
    assert trace.steps[0].thought == "Checking status"
    assert trace.steps[0].content == "All looks good."
    assert len(trace.steps[0].tool_calls) == 1
    assert len(trace.steps[0].tool_results) == 1


def test_recorder_decorator():
    rec = AgentTraceRecorder(task_prompt="Test decorator", agent_model="test-agent")

    @rec.trace_tool("calculator_add")
    def add(a, b):
        return a + b

    res = add(10, 20)
    assert res == 30
    trace = rec.complete()
    assert len(trace.steps) == 1
    assert trace.steps[0].tool_calls[0].name == "calculator_add"
    assert trace.steps[0].tool_results[0].output == "30"


def test_recorder_save_and_load_jsonl():
    rec = AgentTraceRecorder(task_prompt="Persist to file", agent_model="test-agent")
    rec.start_step(role="assistant", content="Step 1 done")
    tc = rec.record_tool_call(name="check", arguments={})
    rec.record_tool_result(call_id=tc.call_id, name="check", output="OK")
    rec.complete()

    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tf:
        temp_path = tf.name

    try:
        rec.save_jsonl(temp_path)
        loaded = AgentTraceRecorder.load_jsonl(temp_path)
        assert loaded.trace_id == rec.trace.trace_id
        assert len(loaded.steps) == 1
        assert loaded.steps[0].tool_calls[0].name == "check"
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
