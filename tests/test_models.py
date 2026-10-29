"""
Tests for AgentTrace models and serialization.
"""

from agenttrace.models import Step, ToolCall, ToolResult, ToolStatus, Trace


def test_trace_jsonl_roundtrip():
    trace = Trace(
        trace_id="tr_roundtrip_1",
        task_prompt="Refactor database indexes",
        agent_model="claude-3-7-sonnet",
        steps=[
            Step(
                step_index=1,
                role="assistant",
                thought="Checking slow queries",
                tool_calls=[ToolCall(call_id="c_sql", name="sql_query", arguments={"q": "EXPLAIN ANALYZE"})],
                tool_results=[ToolResult(call_id="c_sql", name="sql_query", status=ToolStatus.SUCCESS, output="Index scan")],
            )
        ],
    )
    d = trace.to_dict()
    restored = Trace.from_dict(d)

    assert restored.trace_id == "tr_roundtrip_1"
    assert len(restored.steps) == 1
    assert restored.steps[0].tool_calls[0].name == "sql_query"
    assert restored.steps[0].tool_results[0].output == "Index scan"
