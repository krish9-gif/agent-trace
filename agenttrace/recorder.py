"""
AgentTrace Recorder: Lightweight, non-intrusive trajectory recording.
Hardened with safe size bounds, structured validation, and error guards.
"""

from __future__ import annotations
import datetime
import json
import os
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from .models import Step, ToolCall, ToolResult, ToolStatus, Trace


class AgentTraceRecorder:
    """
    Lightweight recorder to capture multi-turn agent interaction steps,
    tool executions, stdout/stderr, and token telemetry.
    """

    MAX_JSONL_READ_BYTES = 50 * 1024 * 1024  # 50MB safety cap

    def __init__(self, trace_id: Optional[str] = None, task_prompt: str = "", agent_model: str = "custom-agent"):
        self.trace_id = trace_id or f"trace_{uuid.uuid4().hex[:12]}"
        self.trace = Trace(
            trace_id=self.trace_id,
            task_prompt=task_prompt,
            agent_model=agent_model,
            started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self._current_step: Optional[Step] = None
        self._step_counter: int = 0

    def start_step(self, role: str = "assistant", thought: str = "", content: str = "") -> Step:
        """Start a new execution step."""
        self._step_counter += 1
        step = Step(
            step_index=self._step_counter,
            role=role,
            thought=thought,
            content=content,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        self._current_step = step
        self.trace.steps.append(step)
        return step

    def record_thought(self, thought: str) -> None:
        """Update thought of current step."""
        if not self._current_step:
            self.start_step(role="assistant")
        self._current_step.thought += (thought if not self._current_step.thought else f"\n{thought}")

    def record_content(self, content: str) -> None:
        """Update content of current step."""
        if not self._current_step:
            self.start_step(role="assistant")
        self._current_step.content += (content if not self._current_step.content else f"\n{content}")

    def record_tool_call(self, name: str, arguments: Dict[str, Any], call_id: Optional[str] = None) -> ToolCall:
        """Record an intended tool invocation."""
        if not self._current_step:
            self.start_step(role="assistant")
        cid = call_id or f"call_{uuid.uuid4().hex[:8]}"
        tc = ToolCall(call_id=cid, name=name, arguments=arguments)
        self._current_step.tool_calls.append(tc)
        return tc

    def record_tool_result(
        self,
        call_id: str,
        name: str,
        status: ToolStatus = ToolStatus.SUCCESS,
        output: str = "",
        exit_code: Optional[int] = 0,
        error_message: Optional[str] = None,
        duration_ms: float = 0.0,
    ) -> ToolResult:
        """Record the execution outcome of a tool call."""
        if not self._current_step:
            self.start_step(role="tool")
        tr = ToolResult(
            call_id=call_id,
            name=name,
            status=status,
            output=output,
            exit_code=exit_code,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        self._current_step.tool_results.append(tr)
        return tr

    def trace_tool(self, tool_name: Optional[str] = None) -> Callable:
        """Decorator to wrap any Python tool function and record its invocation and results."""
        def decorator(func: Callable) -> Callable:
            name = tool_name or func.__name__
            def wrapper(*args, **kwargs) -> Any:
                cid = f"call_{uuid.uuid4().hex[:8]}"
                call_args = {"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}}
                self.record_tool_call(name=name, arguments=call_args, call_id=cid)
                t0 = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    duration = (time.perf_counter() - t0) * 1000.0
                    self.record_tool_result(
                        call_id=cid,
                        name=name,
                        status=ToolStatus.SUCCESS,
                        output=str(result),
                        exit_code=0,
                        duration_ms=duration,
                    )
                    return result
                except Exception as e:
                    duration = (time.perf_counter() - t0) * 1000.0
                    self.record_tool_result(
                        call_id=cid,
                        name=name,
                        status=ToolStatus.ERROR,
                        output="",
                        exit_code=1,
                        error_message=str(e),
                        duration_ms=duration,
                    )
                    raise
            return wrapper
        return decorator

    def complete(self) -> Trace:
        """Finalize the trace with completion timestamp."""
        self.trace.completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return self.trace

    def save_jsonl(self, filepath: str) -> None:
        """Save steps to JSONL format, safely creating parent directories if needed."""
        parent_dir = os.path.dirname(os.path.abspath(filepath))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            header = {
                "type": "TRACE_HEADER",
                "trace_id": self.trace.trace_id,
                "task_prompt": self.trace.task_prompt,
                "agent_model": self.trace.agent_model,
                "started_at": self.trace.started_at,
                "completed_at": self.trace.completed_at,
                "metadata": self.trace.metadata,
            }
            f.write(json.dumps(header) + "\n")
            for step in self.trace.steps:
                row = {"type": "STEP", **step.to_dict()}
                f.write(json.dumps(row) + "\n")

    @classmethod
    def load_jsonl(cls, filepath: str) -> Trace:
        """Load a trace from JSONL format with size bounds and sanitization."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Trace file not found: {filepath}")
        
        file_size = os.path.getsize(filepath)
        if file_size > cls.MAX_JSONL_READ_BYTES:
            raise ValueError(f"Trace file exceeds safety cap ({file_size} > {cls.MAX_JSONL_READ_BYTES} bytes)")

        header = None
        steps_data = []
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                if data.get("type") == "TRACE_HEADER":
                    header = data
                elif data.get("type") == "STEP" or "step_index" in data:
                    steps_data.append(data)

        if not header:
            header = {
                "trace_id": f"trace_loaded_{uuid.uuid4().hex[:6]}",
                "task_prompt": "Loaded trace",
                "agent_model": "unknown",
            }
        
        trace_dict = {
            "trace_id": header.get("trace_id", "trace_unknown"),
            "task_prompt": header.get("task_prompt", ""),
            "agent_model": header.get("agent_model", "unknown"),
            "started_at": header.get("started_at", ""),
            "completed_at": header.get("completed_at"),
            "steps": steps_data,
            "metadata": header.get("metadata", {}),
        }
        return Trace.from_dict(trace_dict)
