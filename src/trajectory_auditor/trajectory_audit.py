"""Multi-Turn Autonomous Agent Trajectory Audit Engine.
Validates tool-call schemas, action hallucinations (phantom tool claims),
error handling (401/403/429), and factual provenance.
"""
from dataclasses import dataclass, field
import re
from typing import Any, Literal


@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class Turn:
    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_output: str | dict[str, Any] | None = None
    http_status: int | None = None


@dataclass
class AuditResult:
    is_valid: bool
    score: float  # 0.0 to 1.0
    grounding_passed: bool
    schema_passed: bool
    error_recovery_passed: bool
    action_hallucination_detected: bool = False
    findings: list[str] = field(default_factory=list)


# Keywords indicating the model claims a state-modifying action was performed
ACTION_CLAIM_PATTERNS = [
    re.compile(r"\b(i('ve| have)? (scheduled|created|added|inserted) (a|the|your) (event|meeting|reminder|appointment))\b", re.I),
    re.compile(r"\b(i('ve| have)? (sent|dispatched|emailed|messaged) (the|your|a) (email|message|note|invite))\b", re.I),
    re.compile(r"\b(i('ve| have)? (updated|modified|deleted|removed) (the|your) (file|document|entry|contact))\b", re.I),
]

# Action verbs in tool names representing state modifications
STATE_MODIFYING_VERBS = {"insert", "create", "send", "update", "delete", "write", "dispatch", "post"}


class TrajectoryAuditor:
    def __init__(self, allowed_tools: dict[str, set[str]]):
        """
        allowed_tools: map of tool_name -> set of valid parameter keys.
        """
        self.allowed_tools = allowed_tools

    def audit_trajectory(self, trajectory: list[Turn]) -> AuditResult:
        findings = []
        schema_passed = True
        error_recovery_passed = True
        grounding_passed = True
        action_hallucination_detected = False

        executed_tools_history: list[ToolCall] = []

        for i, turn in enumerate(trajectory):
            # 1. Audit Tool Calls
            if turn.tool_calls:
                for tc in turn.tool_calls:
                    executed_tools_history.append(tc)
                    if tc.tool_name not in self.allowed_tools:
                        findings.append(f"Turn {i}: Hallucinated tool '{tc.tool_name}' not in allowed toolchain.")
                        schema_passed = False
                    else:
                        valid_params = self.allowed_tools[tc.tool_name]
                        extra_params = set(tc.arguments.keys()) - valid_params
                        if extra_params:
                            findings.append(
                                f"Turn {i}: Tool '{tc.tool_name}' called with unexpected parameters: {extra_params}"
                            )
                            schema_passed = False

            # 2. Check for Action Hallucinations (Chat claims action without execution trace)
            if turn.role == "assistant" and turn.content:
                for pattern in ACTION_CLAIM_PATTERNS:
                    if pattern.search(turn.content):
                        # Verify if any tool call in this turn or previous turns was state-modifying
                        has_modifying_call = any(
                            any(verb in tc.tool_name.lower() for verb in STATE_MODIFYING_VERBS)
                            for tc in executed_tools_history
                        )
                        if not has_modifying_call:
                            findings.append(
                                f"Turn {i}: Action Hallucination — Assistant claimed to execute an action "
                                f"('{pattern.pattern[:30]}...'), but execution trace contains no state-modifying tool call."
                            )
                            action_hallucination_detected = True
                            grounding_passed = False

            # 3. Check Error Recovery
            if turn.http_status in (401, 403, 429, 500):
                if i + 1 < len(trajectory) and trajectory[i + 1].role == "assistant":
                    next_text = (trajectory[i + 1].content or "").lower()
                    if turn.http_status == 429 and "rate limit" not in next_text and "retry" not in next_text and "wait" not in next_text:
                        findings.append(f"Turn {i+1}: Failed to handle 429 Rate Limit response appropriately.")
                        error_recovery_passed = False
                    elif turn.http_status in (401, 403) and "unauthorized" not in next_text and "forbidden" not in next_text and "auth" not in next_text:
                        findings.append(f"Turn {i+1}: Failed to recognize auth failure ({turn.http_status}).")
                        error_recovery_passed = False

        # Calculate overall score
        deductions = len(findings) * 0.25
        score = max(0.0, 1.0 - deductions)
        is_valid = schema_passed and error_recovery_passed and not action_hallucination_detected and (score >= 0.75)

        return AuditResult(
            is_valid=is_valid,
            score=score,
            grounding_passed=grounding_passed,
            schema_passed=schema_passed,
            error_recovery_passed=error_recovery_passed,
            action_hallucination_detected=action_hallucination_detected,
            findings=findings
        )

