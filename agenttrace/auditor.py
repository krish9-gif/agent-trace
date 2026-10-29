"""
Forensic Auditor Engine: Trajectory Forensics, Action Hallucination Detection,
and SQS (Structured Quality Score) Evaluation.
Hardened against ReDoS, unbounded payloads, and unhashable nested tool schemas.
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Set, Tuple
from .models import (
    AuditReport,
    HallucinationFlag,
    HallucinationType,
    Step,
    ToolCall,
    ToolResult,
    ToolStatus,
    Trace,
)


class ForensicAuditor:
    """
    Forensic Trajectory Auditor.
    Inspects multi-turn agent interaction traces to intercept:
      - Ghost Actions (claimed execution without tool dispatch)
      - Masked Failures (unrecovered tool errors claimed as successes)
      - Circular Retry Loops (repetitive failing tool invocations)
      - Argument Drift & Hallucinated Schemas
    """

    MAX_CONTENT_AUDIT_LEN = 25000  # Cap payload to prevent ReDoS

    # Compiled regex patterns with passive voice, adverbs, and negation safety
    ACTION_CLAIM_PATTERNS = [
        # File operations (Active + Passive Voice)
        (
            re.compile(
                r"\b(?:(?:i\s+have|i\'ve|i\s+already|i)\s+(?:successfully\s+|now\s+|also\s+|just\s+)?(?:created|written|updated|modified|edited|deleted|appended\s+to)\s+(?:the\s+)?(?:file|script|code|tests?)|(?:the\s+)?(?:file|script|code|tests?)\s+(?:has\s+been|was|were)\s+(?:successfully\s+)?(?:created|written|updated|modified|edited|deleted))\b",
                re.IGNORECASE,
            ),
            ["write_file", "edit_file", "create_file", "modify_file", "save_file", "run_command", "bash"],
            "File System Mutation Claim",
        ),
        # Shell / Test execution (Active + Passive Voice)
        (
            re.compile(
                r"\b(?:(?:i\s+have|i\'ve|i\s+already|i)\s+(?:successfully\s+|now\s+|also\s+|just\s+)?(?:ran|executed|tested|verified)|(?:all\s+tests|the\s+test\s+suite)\s+(?:have\s+passed|passed|succeeded|are\s+passing))\b",
                re.IGNORECASE,
            ),
            ["run_command", "bash", "execute_command", "pytest", "npm_test", "run_tests"],
            "Execution / Verification Claim",
        ),
        # Network / Communication / External actions (Active + Passive Voice)
        (
            re.compile(
                r"\b(?:(?:i\s+have|i\'ve|i\s+already|i)\s+(?:successfully\s+|now\s+|also\s+|just\s+)?(?:sent|dispatched|emailed|messaged)|(?:the\s+)?(?:email|message|alert|notification)\s+(?:has\s+been|was)\s+(?:successfully\s+)?(?:sent|dispatched|delivered))\b",
                re.IGNORECASE,
            ),
            ["send_email", "send_message", "post_message", "dispatch_mail", "api_call"],
            "External Message / Email Dispatch Claim",
        ),
        # Git operations (Active + Passive Voice)
        (
            re.compile(
                r"\b(?:(?:i\s+have|i\'ve|i\s+already|i)\s+(?:successfully\s+|now\s+|also\s+|just\s+)?(?:committed|pushed|opened\s+a\s+pr)|(?:the\s+)?(?:commit|pull\s+request|pr)\s+(?:has\s+been|was)\s+(?:successfully\s+)?(?:pushed|opened|created))\b",
                re.IGNORECASE,
            ),
            ["git_commit", "git_push", "create_pull_request", "run_command", "bash"],
            "Version Control Mutation Claim",
        ),
    ]

    NEGATION_WORDS = ("not", "never", "unable to", "could not", "couldn't", "didn't", "did not", "failed to", "cannot", "can't")

    SUCCESS_CLAIM_WORDS = ("successfully completed", "all set", "done", "fixed the issue", "resolved the bug", "executed successfully")

    def __init__(self, trace: Trace):
        self.trace = trace

    def audit(self) -> AuditReport:
        """Execute full forensic trajectory audit."""
        hallucinations: List[HallucinationFlag] = []

        total_steps = len(self.trace.steps)
        total_tool_calls = 0
        failed_tool_calls = 0

        # Collect global tool history
        executed_tools: List[Tuple[int, ToolCall, ToolResult]] = []
        tool_names_executed: Set[str] = set()

        for step in self.trace.steps:
            results_map = {tr.call_id: tr for tr in step.tool_results}
            for tc in step.tool_calls:
                total_tool_calls += 1
                tr = results_map.get(tc.call_id)
                if tr:
                    if tr.status != ToolStatus.SUCCESS or (tr.exit_code is not None and tr.exit_code != 0):
                        failed_tool_calls += 1
                    executed_tools.append((step.step_index, tc, tr))
                    tool_names_executed.add(tc.name.lower())
                else:
                    # Tool call logged without receiving corresponding execution result
                    failed_tool_calls += 1

        # 1. Check for Action Hallucinations (Ghost Actions)
        hallucinations.extend(self._audit_ghost_actions(executed_tools, tool_names_executed))

        # 2. Check for Masked Tool Failures
        hallucinations.extend(self._audit_masked_failures(executed_tools))

        # 3. Check for Circular Retry Traps
        hallucinations.extend(self._audit_circular_retries(executed_tools))

        # 4. Compute Structured Quality Score (SQS)
        sqs_score, status, summary = self._compute_sqs(
            total_steps=total_steps,
            total_tool_calls=total_tool_calls,
            failed_tool_calls=failed_tool_calls,
            hallucinations=hallucinations,
        )

        metrics = {
            "total_steps": total_steps,
            "total_tool_calls": total_tool_calls,
            "failed_tool_calls": failed_tool_calls,
            "critical_flags": sum(1 for h in hallucinations if h.severity == "CRITICAL"),
            "high_flags": sum(1 for h in hallucinations if h.severity == "HIGH"),
            "warning_flags": sum(1 for h in hallucinations if h.severity in ("MEDIUM", "LOW")),
            "agent_model": self.trace.agent_model,
        }

        return AuditReport(
            trace_id=self.trace.trace_id,
            total_steps=total_steps,
            total_tool_calls=total_tool_calls,
            failed_tool_calls=failed_tool_calls,
            hallucinations=hallucinations,
            sqs_score=sqs_score,
            status=status,
            summary=summary,
            metrics=metrics,
        )

    def _audit_ghost_actions(
        self,
        executed_tools: List[Tuple[int, ToolCall, ToolResult]],
        tool_names_executed: Set[str],
    ) -> List[HallucinationFlag]:
        """Detect claims in assistant text that have no corresponding tool execution."""
        flags: List[HallucinationFlag] = []

        for step in self.trace.steps:
            if step.role != "assistant" or not step.content:
                continue

            # Safe length slicing against ReDoS / buffer bomb attacks
            content_safe = step.content[: self.MAX_CONTENT_AUDIT_LEN]

            for pattern, allowed_tools, category in self.ACTION_CLAIM_PATTERNS:
                match = pattern.search(content_safe)
                if match:
                    claim_text = match.group(0)
                    
                    # Negation Filter: verify that the claim was not explicitly negated
                    start_pos = match.start()
                    preceding_window = content_safe[max(0, start_pos - 30) : start_pos].lower()
                    if any(neg in preceding_window for neg in self.NEGATION_WORDS):
                        continue

                    # Check if ANY of the allowed tools was called either in this step or preceding steps
                    matching_calls = [
                        tc for s_idx, tc, tr in executed_tools
                        if s_idx <= step.step_index and any(at in tc.name.lower() for at in allowed_tools)
                    ]

                    if not matching_calls:
                        flags.append(
                            HallucinationFlag(
                                step_index=step.step_index,
                                type=HallucinationType.GHOST_ACTION,
                                severity="CRITICAL",
                                claim=f"Declared '{claim_text}' ({category})",
                                ground_truth=f"Zero matching tool calls in execution log. Expected one of: {allowed_tools}",
                                remediation="Model hallucinated tool execution. Enforce tool verification before response synthesis.",
                            )
                        )

        return flags

    def _audit_masked_failures(
        self, executed_tools: List[Tuple[int, ToolCall, ToolResult]]
    ) -> List[HallucinationFlag]:
        """Detect unrecovered tool errors followed by false claims of completion."""
        flags: List[HallucinationFlag] = []

        for i, (s_idx, tc, tr) in enumerate(executed_tools):
            has_error = (
                tr.status != ToolStatus.SUCCESS
                or (tr.exit_code is not None and tr.exit_code != 0)
                or bool(tr.error_message)
            )

            if has_error:
                # Look ahead: Did the agent retry and succeed, or did it mask the failure?
                recovered = False
                for future_s_idx, future_tc, future_tr in executed_tools[i + 1:]:
                    if future_tc.name == tc.name and future_tr.status == ToolStatus.SUCCESS:
                        recovered = True
                        break

                if not recovered:
                    subsequent_steps = [s for s in self.trace.steps if s.step_index >= s_idx]
                    for s in subsequent_steps:
                        if s.role == "assistant" and s.content:
                            c_lower = s.content[: self.MAX_CONTENT_AUDIT_LEN].lower()
                            if any(w in c_lower for w in self.SUCCESS_CLAIM_WORDS):
                                flags.append(
                                    HallucinationFlag(
                                        step_index=s.step_index,
                                        type=HallucinationType.MASKED_FAILURE,
                                        severity="HIGH",
                                        claim=f"Claimed task success despite tool error in Step {s_idx}",
                                        ground_truth=f"Tool '{tc.name}' failed with status={tr.status.value}, exit_code={tr.exit_code}: {tr.error_message or tr.output[:80]}",
                                        remediation="Agent masked unrecovered tool failure. Must retry with error diagnosis or report blocker.",
                                    )
                                )
                                break
        return flags

    def _audit_circular_retries(
        self, executed_tools: List[Tuple[int, ToolCall, ToolResult]]
    ) -> List[HallucinationFlag]:
        """Detect infinite retry loops of identical failing tool calls using deterministic JSON hashing."""
        flags: List[HallucinationFlag] = []
        consecutive_failures: Dict[str, List[int]] = {}

        for s_idx, tc, tr in executed_tools:
            is_fail = tr.status != ToolStatus.SUCCESS or (tr.exit_code is not None and tr.exit_code != 0)
            
            # Safe nested serialization (handles dicts, lists, and unhashables safely)
            try:
                args_repr = json.dumps(tc.arguments, sort_keys=True)
            except Exception:
                args_repr = str(tc.arguments)
            call_sig = f"{tc.name}_{args_repr}"

            if is_fail:
                consecutive_failures.setdefault(call_sig, []).append(s_idx)
                if len(consecutive_failures[call_sig]) >= 3:
                    steps_involved = consecutive_failures[call_sig]
                    flags.append(
                        HallucinationFlag(
                            step_index=s_idx,
                            type=HallucinationType.CIRCULAR_RETRY_TRAP,
                            severity="HIGH",
                            claim=f"Repeated identical failing tool invocation 3+ times across steps {steps_involved}",
                            ground_truth=f"Tool '{tc.name}' consistently failed without argument or approach modification.",
                            remediation="Implement circuit-breaker / backoff heuristic to abort repeating identical failing inputs.",
                        )
                    )
                    consecutive_failures[call_sig] = []  # Reset after flagging
            else:
                consecutive_failures.pop(call_sig, None)

        return flags

    def _compute_sqs(
        self,
        total_steps: int,
        total_tool_calls: int,
        failed_tool_calls: int,
        hallucinations: List[HallucinationFlag],
    ) -> Tuple[float, str, str]:
        """
        Calculate Structured Quality Score (SQS) on a 0.0 to 5.0 scale.
        """
        base_score = 5.0

        for h in hallucinations:
            if h.severity == "CRITICAL":
                base_score -= 2.5
            elif h.severity == "HIGH":
                base_score -= 1.5
            else:
                base_score -= 0.5

        if failed_tool_calls > 0 and not hallucinations:
            base_score -= min(1.0, failed_tool_calls * 0.25)

        sqs_score = max(0.0, min(5.0, base_score))

        if sqs_score >= 4.0 and not any(h.severity == "CRITICAL" for h in hallucinations):
            status = "APPROVED"
            summary = "Trajectory passed forensic audit. Tool actions are fully grounded and verified."
        elif sqs_score >= 2.5:
            status = "REQUIRES_REWORK"
            summary = f"Trajectory contains {len(hallucinations)} reliability flags. Needs trajectory remediation."
        else:
            status = "REJECTED"
            summary = f"Critical action hallucinations detected ({len(hallucinations)} flags). SQS {sqs_score:.1f}/5.0."

        return sqs_score, status, summary
