"""
Two-Tier Deterministic PyTest Verification Suite for Task 01
Tier 1: Smoke & Invariant Validation (< 1s)
Tier 2: Exhaustive Causality & Cryptographic SHA-256 State Assertions
"""

from __future__ import annotations
import hashlib
import json
import os
import pytest

OUTPUT_PATH = os.environ.get("TASK_OUTPUT_PATH", "/workspace/state_output.json")
EXPECTED_GOLDEN_SHA256 = "7c942ec1c0bb5088399a894cdd098a97be471543eb9b355cecfb52b57c4ac9ae"


# =====================================================================
# TIER 1: SMOKE INVARIANTS & INTEGRITY CHECKS
# =====================================================================

def test_tier1_smoke_output_file_exists():
    """Verify that the candidate produced the target output file."""
    assert os.path.exists(OUTPUT_PATH), f"Target output file missing at: {OUTPUT_PATH}"
    assert os.path.getsize(OUTPUT_PATH) > 0, "Target output file is completely empty."


def test_tier1_smoke_valid_json_structure():
    """Verify that the output file is valid JSON with required schema fields."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    required_keys = ["status", "total_events_processed", "committed_transactions", "discarded_transactions", "state", "sha256_checksum"]
    for k in required_keys:
        assert k in data, f"Required top-level key '{k}' missing from output JSON."

    assert data["status"] == "reconciled", f"Expected status 'reconciled', got '{data['status']}'"
    assert isinstance(data["state"], dict), "The 'state' field must be a JSON dictionary."


# =====================================================================
# TIER 2: DEEP CAUSALITY & CRYPTOGRAPHIC STATE ASSERTIONS
# =====================================================================

def test_tier2_deep_rollback_isolation():
    """Assert that rolled-back transactions (tx_beta) are completely excluded from state."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    state = data["state"]
    assert "max_connections" not in state, "State leak detected: 'max_connections' from rolled-back tx_beta was included in state!"


def test_tier2_deep_temporal_causality():
    """Assert that newer committed transactions overwrite older committed mutations."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    state = data["state"]
    # tx_delta (t=110.0, value=7200) should overwrite tx_alpha (t=100.0, value=3600)
    assert state.get("session_timeout") == 7200, f"Expected session_timeout to be 7200, got {state.get('session_timeout')}"
    assert state.get("feature_flag_v2") == "enabled"
    assert state.get("rate_limit_rpm") == 1000


def test_tier2_deep_cryptographic_checksum_match():
    """Mathematically verify that the canonical state matches the golden SHA-256 digest."""
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    state = data["state"]
    canonical_repr = json.dumps(state, sort_keys=True, separators=(",", ":"))
    recomputed_digest = hashlib.sha256(canonical_repr.encode("utf-8")).hexdigest()

    assert data["sha256_checksum"] == recomputed_digest, "Reported sha256_checksum does not match canonical recomputed hash."
    assert data["sha256_checksum"] == EXPECTED_GOLDEN_SHA256, (
        f"Cryptographic divergence: expected golden digest {EXPECTED_GOLDEN_SHA256}, got {data['sha256_checksum']}"
    )
