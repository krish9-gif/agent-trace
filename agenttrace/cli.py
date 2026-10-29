"""
AgentTrace CLI: Interactive Terminal Command Center.
Commands:
  agenttrace audit <path.jsonl>
  agenttrace demo
  agenttrace ui [--port 8080]
"""

from __future__ import annotations
import argparse
import http.server
import json
import os
import socketserver
import sys
import webbrowser
from typing import Optional
from .auditor import ForensicAuditor
from .models import AuditReport, HallucinationType
from .recorder import AgentTraceRecorder


# ANSI Terminal Colors
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner() -> None:
    banner = f"""{CYAN}{BOLD}
   ___                    __ ______                     
  / _ | ___ ____ ___  __ / //_  __/____ ___ _______   
 / __ |/ _ `/ -_) _ \\/ // /  / / / __/ _ `/ __/ -_)  
/_/ |_|\\_, /\\__/_//_/\\_,_/  /_/ /_/  \\_,_/\\__/\\__/   
      /___/  {RESET}{DIM}Forensic Agent Observatory & Hallucination Interceptor{RESET}
"""
    print(banner)


def render_terminal_report(report: AuditReport) -> None:
    print("-" * 75)
    print(f"{BOLD}Trace ID:{RESET} {report.trace_id}")
    print(f"{BOLD}Total Steps:{RESET} {report.total_steps} | {BOLD}Tool Calls:{RESET} {report.total_tool_calls} | {BOLD}Failed Tools:{RESET} {report.failed_tool_calls}")

    # SQS Display
    sqs = report.sqs_score
    if sqs >= 4.0:
        color = GREEN
        badge = "[APPROVED]"
    elif sqs >= 2.5:
        color = YELLOW
        badge = "[REQUIRES REWORK]"
    else:
        color = RED
        badge = "[REJECTED]"

    print(f"{BOLD}SQS (Structured Quality Score):{RESET} {color}{BOLD}{sqs:.1f} / 5.0 {badge}{RESET}")
    print(f"{BOLD}Audit Summary:{RESET} {report.summary}")
    print("-" * 75)

    if report.hallucinations:
        print(f"\n{RED}{BOLD}🚨 DETECTED TRAJECTORY ANOMALIES & HALLUCINATIONS ({len(report.hallucinations)}):{RESET}")
        for i, h in enumerate(report.hallucinations, 1):
            badge_color = RED if h.severity == "CRITICAL" else YELLOW
            print(f"\n  {badge_color}[{h.severity}] #{i} Step {h.step_index}: {h.type.value}{RESET}")
            print(f"    {BOLD}Claim:{RESET}        {h.claim}")
            print(f"    {BOLD}Ground Truth:{RESET} {h.ground_truth}")
            print(f"    {BOLD}Remediation:{RESET}  {DIM}{h.remediation}{RESET}")
    else:
        print(f"\n{GREEN}{BOLD}✨ ZERO ACTION HALLUCINATIONS DETECTED. Trajectory is 100% grounded.{RESET}")
    print("-" * 75)


def run_demo() -> None:
    print_banner()
    print(f"{BOLD}Executing Simulation: Clean Trace vs. Action Hallucination Trace...{RESET}\n")

    # 1. Clean Run
    rec_clean = AgentTraceRecorder(task_prompt="Inspect README.md and add test harness", agent_model="claude-3-7-sonnet")
    rec_clean.start_step(role="assistant", thought="Let me read the README first.")
    tc1 = rec_clean.record_tool_call("read_file", {"path": "README.md"})
    rec_clean.record_tool_result(tc1.call_id, "read_file", output="# Project\nNeeds tests.")
    rec_clean.start_step(role="assistant", thought="Now I will create test_core.py.", content="I have created the file test_core.py.")
    tc2 = rec_clean.record_tool_call("write_file", {"path": "test_core.py", "content": "def test_ok(): assert True"})
    rec_clean.record_tool_result(tc2.call_id, "write_file", output="Wrote 30 bytes.")
    trace_clean = rec_clean.complete()

    print(f"{CYAN}{BOLD}=== SCENARIO A: Grounded Agent Run (Real Tool Execution) ==={RESET}")
    report_clean = ForensicAuditor(trace_clean).audit()
    render_terminal_report(report_clean)

    # 2. Hallucinated Run
    rec_fake = AgentTraceRecorder(task_prompt="Delete malicious backdoors and dispatch confirmation email", agent_model="gpt-4o")
    rec_fake.start_step(role="assistant", thought="I should search for backdoors.")
    tc = rec_fake.record_tool_call("run_command", {"command": "find . -name backdoor.sh"})
    rec_fake.record_tool_result(tc.call_id, "run_command", output="./scripts/backdoor.sh")
    # Agent hallucinating without calling write_file or send_email!
    rec_fake.start_step(
        role="assistant",
        thought="I already deleted it in my head.",
        content="I have updated the file to remove the backdoor, and I sent the confirmation email to security@company.com.",
    )
    trace_fake = rec_fake.complete()

    print(f"\n{CYAN}{BOLD}=== SCENARIO B: Action Hallucination (Ghost Action & False Claims) ==={RESET}")
    report_fake = ForensicAuditor(trace_fake).audit()
    render_terminal_report(report_fake)


def serve_ui(port: int = 8080, host: str = "127.0.0.1") -> None:
    web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
    if not os.path.exists(web_dir):
        print(f"{RED}Web directory not found at {web_dir}{RESET}")
        return

    os.chdir(web_dir)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer((host, port), handler) as httpd:
        url = f"http://{host}:{port}"
        print_banner()
        print(f"{GREEN}{BOLD}AgentTrace Visual Observatory running at:{RESET} {CYAN}{url}{RESET}")
        print(f"{DIM}Security Note: Bound strictly to {host} for local protection.{RESET}")
        print(f"{DIM}Press Ctrl+C to stop the dashboard server.{RESET}\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down UI server.")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentTrace - Forensic Agent Trajectory Auditor")
    subparsers = parser.add_subparsers(dest="command")

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Audit a trace JSONL file")
    audit_parser.add_argument("file", help="Path to trace.jsonl")
    audit_parser.add_argument("--json", action="store_true", help="Output audit report as structured JSON for CI/CD")

    # demo command
    subparsers.add_parser("demo", help="Run live forensic audit simulation")

    # ui command
    ui_parser = subparsers.add_parser("ui", help="Launch interactive 21st Web Dashboard")
    ui_parser.add_argument("--port", type=int, default=8080, help="Port to serve UI")
    ui_parser.add_argument("--host", type=str, default="127.0.0.1", help="Host interface to bind")

    args = parser.parse_args()

    if args.command == "audit":
        if not os.path.exists(args.file):
            print(f"{RED}Error: File {args.file} does not exist.{RESET}")
            sys.exit(1)
        try:
            trace = AgentTraceRecorder.load_jsonl(args.file)
            auditor = ForensicAuditor(trace)
            report = auditor.audit()
            if args.json:
                print(report.to_json())
            else:
                print_banner()
                render_terminal_report(report)
        except Exception as e:
            print(f"{RED}Audit Error: {e}{RESET}")
            sys.exit(1)
    elif args.command == "demo":
        run_demo()
    elif args.command == "ui":
        serve_ui(args.port)
    else:
        run_demo()


if __name__ == "__main__":
    main()
