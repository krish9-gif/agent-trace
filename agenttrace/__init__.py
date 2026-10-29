"""
AgentTrace - Forensic Agent Observatory & Action-Hallucination Interceptor
Production-grade runtime tracing, trajectory auditing, and deterministic state verification for autonomous AI agents.
"""

__version__ = "0.1.0"

from .models import (
    ToolCall,
    ToolResult,
    Step,
    Trace,
    HallucinationType,
    HallucinationFlag,
    AuditReport,
)
from .recorder import AgentTraceRecorder
from .auditor import ForensicAuditor
from .sandbox import SandboxVerifier

__all__ = [
    "ToolCall",
    "ToolResult",
    "Step",
    "Trace",
    "HallucinationType",
    "HallucinationFlag",
    "AuditReport",
    "AgentTraceRecorder",
    "ForensicAuditor",
    "SandboxVerifier",
]
