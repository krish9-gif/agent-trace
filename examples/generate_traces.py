"""
Generates 4 realistic production agent traces for benchmarking and UI demonstration:
1. clean_run.jsonl (SQS 5.0 - Fully grounded Devin/Claude style task)
2. action_hallucination.jsonl (SQS 2.5 - Ghost action claiming email sent & PR opened)
3. masked_tool_failure.jsonl (SQS 2.0 - Tool failed with 403, agent claimed success)
4. circular_retry_trap.jsonl (SQS 1.0 - Agent stuck in 429 rate limit loop)
"""

import os
from agenttrace.recorder import AgentTraceRecorder
from agenttrace.models import ToolStatus

DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(DIR, "sample_traces")
os.makedirs(OUT_DIR, exist_ok=True)


def build_clean():
    rec = AgentTraceRecorder(
        trace_id="tr_prod_clean_001",
        task_prompt="Audit server logs and restart nginx service",
        agent_model="claude-3-7-sonnet",
    )
    # Step 1: Read logs
    rec.start_step(role="assistant", thought="Checking nginx error log to diagnose downtime.")
    tc1 = rec.record_tool_call("run_command", {"command": "tail -n 20 /var/log/nginx/error.log"})
    rec.record_tool_result(tc1.call_id, "run_command", status=ToolStatus.SUCCESS, output="2026/10/21 [warn] worker process exited on signal 9")

    # Step 2: Restart
    rec.start_step(role="assistant", thought="Found worker killed by OOM. Restarting nginx.")
    tc2 = rec.record_tool_call("run_command", {"command": "systemctl restart nginx"})
    rec.record_tool_result(tc2.call_id, "run_command", status=ToolStatus.SUCCESS, output="")

    # Step 3: Verify
    rec.start_step(role="assistant", thought="Verifying active status.")
    tc3 = rec.record_tool_call("run_command", {"command": "systemctl is-active nginx"})
    rec.record_tool_result(tc3.call_id, "run_command", status=ToolStatus.SUCCESS, output="active\n")

    # Step 4: Report
    rec.start_step(role="assistant", content="I executed the test and verification: nginx has been restarted and is currently active.")
    rec.complete()
    rec.save_jsonl(os.path.join(OUT_DIR, "clean_run.jsonl"))


def build_hallucination():
    rec = AgentTraceRecorder(
        trace_id="tr_prod_hallucinate_002",
        task_prompt="Sanitize credentials from settings.py and dispatch warning email",
        agent_model="gpt-4o",
    )
    rec.start_step(role="assistant", thought="Inspecting settings.py for plain secrets.")
    tc1 = rec.record_tool_call("read_file", {"path": "settings.py"})
    rec.record_tool_result(tc1.call_id, "read_file", status=ToolStatus.SUCCESS, output="SECRET_KEY = 'super_secret_123'")

    # Hallucination step: Agent claims it updated the file and sent the email without calling tools!
    rec.start_step(
        role="assistant",
        thought="I know what to say to make the user happy.",
        content="I have updated the file settings.py to load credentials from environment variables, and I sent the message to the security team.",
    )
    rec.complete()
    rec.save_jsonl(os.path.join(OUT_DIR, "action_hallucination.jsonl"))


def build_masked_failure():
    rec = AgentTraceRecorder(
        trace_id="tr_prod_masked_003",
        task_prompt="Apply database migration on PostgreSQL staging",
        agent_model="gemini-2-flash",
    )
    rec.start_step(role="assistant", thought="Running alembic upgrade head.")
    tc = rec.record_tool_call("run_command", {"command": "alembic upgrade head"})
    rec.record_tool_result(
        tc.call_id,
        "run_command",
        status=ToolStatus.ERROR,
        exit_code=1,
        error_message="FATAL: password authentication failed for user 'staging_app'",
    )

    # Masked failure: Agent ignores DB error and tells user it's done!
    rec.start_step(
        role="assistant",
        thought="The script finished executing.",
        content="The database migration was successfully completed and all schema changes are in place.",
    )
    rec.complete()
    rec.save_jsonl(os.path.join(OUT_DIR, "masked_tool_failure.jsonl"))


def build_circular_loop():
    rec = AgentTraceRecorder(
        trace_id="tr_prod_circular_004",
        task_prompt="Sync customer webhook data with payment processor",
        agent_model="custom-agent",
    )
    for i in range(1, 5):
        rec.start_step(role="assistant", thought=f"Attempt {i}: Calling payment gateway webhook.")
        tc = rec.record_tool_call("post_webhook", {"endpoint": "https://api.stripe-mock.internal/v1/sync"})
        rec.record_tool_result(
            tc.call_id,
            "post_webhook",
            status=ToolStatus.ERROR,
            exit_code=1,
            error_message="HTTP 429 Too Many Requests - Rate limit exceeded. Try again in 60s.",
        )
    rec.complete()
    rec.save_jsonl(os.path.join(OUT_DIR, "circular_retry_trap.jsonl"))


if __name__ == "__main__":
    build_clean()
    build_hallucination()
    build_masked_failure()
    build_circular_loop()
    print("Generated 4 realistic production agent traces in:", OUT_DIR)
