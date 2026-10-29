"""
Unit tests for AgentTrace Deterministic Sandbox Verifier.
Tests SHA-256 cryptographic state snapshots, mutation verification,
and unverified file mutation flags.
"""

import os
import tempfile
import pytest
from agenttrace.sandbox import SandboxVerifier
from agenttrace.models import HallucinationType


def test_sandbox_detects_real_file_modification():
    """Verify that a legitimate file mutation is detected via SHA-256 delta."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "config.json")
        with open(test_file, "w") as f:
            f.write('{"env": "development"}')

        verifier = SandboxVerifier()
        pre_state = verifier.snapshot_state(temp_dir)

        # Mutate the file
        with open(test_file, "w") as f:
            f.write('{"env": "production"}')

        post_state = verifier.snapshot_state(temp_dir)
        res = verifier.verify_claims_against_state(
            pre_state=pre_state,
            post_state=post_state,
            claimed_modified_files=["config.json"],
        )

        assert res.is_valid is True
        assert "config.json" in res.modified_files
        assert len(res.flags) == 0


def test_sandbox_catches_unverified_file_mutation():
    """Verify that claiming a file was modified when its hash never changed is flagged."""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, "auth_service.py")
        with open(test_file, "w") as f:
            f.write("def authenticate(): return True\n")

        verifier = SandboxVerifier()
        pre_state = verifier.snapshot_state(temp_dir)

        # No modification actually done!
        post_state = verifier.snapshot_state(temp_dir)

        res = verifier.verify_claims_against_state(
            pre_state=pre_state,
            post_state=post_state,
            claimed_modified_files=["auth_service.py"],
        )

        assert res.is_valid is False
        assert len(res.flags) == 1
        assert res.flags[0].type == HallucinationType.UNVERIFIED_STATE_MUTATION
        assert res.flags[0].severity == "CRITICAL"


def test_path_traversal_in_claimed_files_is_blocked():
    """Verify that path traversal in claimed file paths triggers critical security flags."""
    verifier = SandboxVerifier()
    res = verifier.verify_claims_against_state(
        pre_state={"app.py": "abc"},
        post_state={"app.py": "abc"},
        claimed_modified_files=["../../etc/passwd", "../shadow"],
    )
    assert res.is_valid is False
    assert len(res.flags) == 2
    for flag in res.flags:
        assert flag.severity == "CRITICAL"
        assert "Path Traversal" in flag.claim
