"""Comprehensive test suite verifying all portfolio modules."""
import pytest
from pathlib import Path
from src.harness.security import assert_safe_path
from src.harness.ctrf_reporter import CTRFReport, CTRFTest
from src.harness.eval_harness import TwoTierEvalHarness
from src.trajectory_auditor.trajectory_audit import TrajectoryAuditor, Turn, ToolCall
from src.benchmarks.dag_reconciliation import DistributedDAGReconciler, LogEvent
from src.benchmarks.quantized_kernel import assert_matrix_shape_supported, verify_numerical_tolerance


def test_safe_path_containment(tmp_path):
    sub = tmp_path / "sandbox" / "test.txt"
    sub.parent.mkdir(parents=True, exist_ok=True)
    sub.write_text("ok")

    safe = assert_safe_path(tmp_path, sub)
    assert safe == sub.resolve()

    with pytest.raises(PermissionError):
        assert_safe_path(tmp_path, tmp_path / ".." / "etc" / "passwd")


def test_ctrf_reporter():
    rep = CTRFReport()
    rep.add_test(CTRFTest(name="test_1", status="passed", duration=12.5))
    rep.add_test(CTRFTest(name="test_2", status="failed", duration=25.0, message="Fail"))
    res = rep.finalize()
    assert res["summary"]["tests"] == 2
    assert res["summary"]["passed"] == 1
    assert res["summary"]["failed"] == 1


def test_two_tier_harness(tmp_path):
    harness = TwoTierEvalHarness(tmp_path)
    harness.register_smoke("syntax_valid", lambda: True)
    harness.register_deep("integration_check", lambda: True)

    result = harness.run()
    assert result["success"] is True
    assert result["tier"] == "completed"
    assert result["report"]["summary"]["passed"] == 2


def test_two_tier_harness_smoke_abort(tmp_path):
    harness = TwoTierEvalHarness(tmp_path)
    harness.register_smoke("syntax_valid", lambda: False)
    deep_called = False

    def deep_fn():
        nonlocal deep_called
        deep_called = True
        return True

    harness.register_deep("integration_check", deep_fn)
    result = harness.run()

    assert result["success"] is False
    assert result["tier"] == "smoke_failed"
    assert deep_called is False  # Deep check was correctly skipped!


def test_trajectory_auditor():
    allowed = {
        "query_database": {"query", "limit"},
        "fetch_api": {"endpoint", "method"}
    }
    auditor = TrajectoryAuditor(allowed_tools=allowed)

    # Valid turn sequence
    traj = [
        Turn(role="user", content="Fetch data"),
        Turn(role="assistant", tool_calls=[ToolCall("query_database", {"query": "SELECT *", "limit": 10})]),
        Turn(role="tool", content="10 records returned", http_status=200),
        Turn(role="assistant", content="Here are the 10 records found.")
    ]
    res = auditor.audit_trajectory(traj)
    assert res.is_valid is True
    assert res.score == 1.0


def test_trajectory_auditor_catches_hallucination():
    allowed = {"query_database": {"query"}}
    auditor = TrajectoryAuditor(allowed_tools=allowed)

    # Calling unapproved tool
    traj = [
        Turn(role="assistant", tool_calls=[ToolCall("hack_system", {"target": "admin"})])
    ]
    res = auditor.audit_trajectory(traj)
    assert res.is_valid is False
    assert any("Hallucinated tool" in f for f in res.findings)


def test_trajectory_auditor_catches_action_hallucination():
    allowed = {
        "contacts_search": {"name"},
        "calendar_insert": {"event", "time"}
    }
    auditor = TrajectoryAuditor(allowed_tools=allowed)

    # Agent performs read-only contact lookup, then claims in chat it scheduled the meeting
    traj = [
        Turn(role="user", content="Schedule a meeting with Dr. Mehta for tomorrow at 3 PM."),
        Turn(role="assistant", tool_calls=[ToolCall("contacts_search", {"name": "Dr. Mehta"})]),
        Turn(role="tool", content="Found Dr. Mehta (mehta@example.com)", http_status=200),
        Turn(role="assistant", content="I have scheduled your meeting with Dr. Mehta for tomorrow at 3 PM!")
    ]
    res = auditor.audit_trajectory(traj)
    assert res.is_valid is False
    assert res.action_hallucination_detected is True
    assert res.grounding_passed is False
    assert any("Action Hallucination" in f for f in res.findings)


def test_dag_reconciliation():
    reconciler = DistributedDAGReconciler()
    # Transaction 1: valid
    reconciler.add_event(LogEvent(timestamp=100.0, node_id="node1", action="MUTATE", key="counter", value=1, tx_id="tx_1"))
    # Transaction 2: rolled back
    reconciler.add_event(LogEvent(timestamp=105.0, node_id="node2", action="MUTATE", key="counter", value=99, tx_id="tx_2"))
    reconciler.add_event(LogEvent(timestamp=110.0, node_id="node1", action="ROLLBACK", key="counter", value=None, tx_id="tx_2"))
    # Transaction 3: valid commit
    reconciler.add_event(LogEvent(timestamp=115.0, node_id="node1", action="MUTATE", key="counter", value=2, tx_id="tx_3"))

    final_state = reconciler.reconcile()
    assert final_state["counter"] == 2  # Rolled back tx_2 was correctly ignored


def test_quantized_kernel_tolerances():
    assert assert_matrix_shape_supported(1000, 1000, allow_ragged=True) is True
    with pytest.raises(ValueError):
        assert_matrix_shape_supported(1000, 1000, allow_ragged=False)

    cand = [1.00005, 2.00008]
    ref = [1.0, 2.0]
    assert verify_numerical_tolerance(cand, ref, rtol=1e-4) is True
