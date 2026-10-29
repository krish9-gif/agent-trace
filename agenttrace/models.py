"""
Core data structures for AgentTrace using Python dataclasses and standard typing.
Ponytail Standard: Zero external dependencies, fast JSON serialization, strict types.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import datetime
import json


class HallucinationType(str, Enum):
    GHOST_ACTION = "GHOST_ACTION"  # Claimed action done in text, but tool was never called
    MASKED_FAILURE = "MASKED_FAILURE"  # Tool failed (non-zero or error), but model claimed success
    ARGUMENT_DRIFT = "ARGUMENT_DRIFT"  # Tool arguments contained hallucinated or invalid schemas
    CIRCULAR_RETRY_TRAP = "CIRCULAR_RETRY_TRAP"  # Identical failing tool calls repeated >= 3 times
    UNVERIFIED_STATE_MUTATION = "UNVERIFIED_STATE_MUTATION"  # File/state claimed modified, but hash was unchanged


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"

    @classmethod
    def from_str(cls, val: Any) -> ToolStatus:
        if not val:
            return cls.SUCCESS
        val_str = str(val).lower().strip()
        try:
            return cls(val_str)
        except ValueError:
            if any(k in val_str for k in ("err", "fail", "fatal", "broken")):
                return cls.ERROR
            if "time" in val_str:
                return cls.TIMEOUT
            return cls.SUCCESS


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ToolResult:
    call_id: str
    name: str
    status: ToolStatus
    output: str = ""
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class Step:
    step_index: int
    role: str
    thought: str = ""
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tool_results: List[ToolResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "role": self.role,
            "thought": self.thought,
            "content": self.content,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "tool_results": [tr.to_dict() for tr in self.tool_results],
            "timestamp": self.timestamp,
        }


@dataclass
class Trace:
    trace_id: str
    task_prompt: str
    agent_model: str
    started_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    completed_at: Optional[str] = None
    steps: List[Step] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "task_prompt": self.task_prompt,
            "agent_model": self.agent_model,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Trace:
        steps = []
        for s in data.get("steps", []):
            tool_calls = [
                ToolCall(
                    call_id=tc["call_id"],
                    name=tc["name"],
                    arguments=tc.get("arguments", {}),
                    timestamp=tc.get("timestamp", ""),
                )
                for tc in s.get("tool_calls", [])
            ]
            tool_results = [
                ToolResult(
                    call_id=tr.get("call_id", "unknown_call"),
                    name=tr.get("name", "unknown_tool"),
                    status=ToolStatus.from_str(tr.get("status")),
                    output=tr.get("output", ""),
                    exit_code=tr.get("exit_code"),
                    error_message=tr.get("error_message"),
                    duration_ms=float(tr.get("duration_ms", 0.0)),
                    timestamp=tr.get("timestamp", ""),
                )
                for tr in s.get("tool_results", [])
            ]
            steps.append(
                Step(
                    step_index=s["step_index"],
                    role=s["role"],
                    thought=s.get("thought", ""),
                    content=s.get("content", ""),
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                    timestamp=s.get("timestamp", ""),
                )
            )
        return cls(
            trace_id=data["trace_id"],
            task_prompt=data["task_prompt"],
            agent_model=data.get("agent_model", "unknown"),
            started_at=data.get("started_at", ""),
            completed_at=data.get("completed_at"),
            steps=steps,
            metadata=data.get("metadata", {}),
        )


@dataclass
class HallucinationFlag:
    step_index: int
    type: HallucinationType
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    claim: str
    ground_truth: str
    remediation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "type": self.type.value,
            "severity": self.severity,
            "claim": self.claim,
            "ground_truth": self.ground_truth,
            "remediation": self.remediation,
        }


@dataclass
class AuditReport:
    trace_id: str
    total_steps: int
    total_tool_calls: int
    failed_tool_calls: int
    hallucinations: List[HallucinationFlag]
    sqs_score: float  # 0.0 to 5.0 (Standard Quality Score)
    status: str  # "APPROVED" | "REJECTED" | "REQUIRES_REWORK"
    summary: str
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_steps": self.total_steps,
            "total_tool_calls": self.total_tool_calls,
            "failed_tool_calls": self.failed_tool_calls,
            "hallucination_count": len(self.hallucinations),
            "hallucinations": [h.to_dict() for h in self.hallucinations],
            "sqs_score": round(self.sqs_score, 2),
            "status": self.status,
            "summary": self.summary,
            "metrics": self.metrics,
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)
