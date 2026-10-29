"""
Deterministic Sandbox State Verifier:
Replays agent actions in an isolated ephemeral environment and uses SHA-256 cryptographic
state hashing to verify ground-truth filesystem mutations versus claimed edits.
Hardened with strict path jail validation, symlink traversal prevention, and safe bounds.
"""

from __future__ import annotations
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from .models import HallucinationFlag, HallucinationType


class SecurityException(Exception):
    """Raised when an operation attempts directory traversal or symlink escape."""
    pass


def assert_safe_path(base_dir: str, target_path: str) -> str:
    """
    Enforce strict path jail. Verifies that target_path resolves strictly
    inside base_dir without symlink escapes or directory traversal attacks.
    """
    base_resolved = os.path.realpath(os.path.abspath(base_dir))
    if os.path.isabs(target_path):
        target_resolved = os.path.realpath(os.path.abspath(target_path))
    else:
        target_resolved = os.path.realpath(os.path.abspath(os.path.join(base_resolved, target_path)))

    try:
        common = os.path.commonpath([base_resolved, target_resolved])
    except ValueError:
        raise SecurityException(f"Cross-drive or invalid path access: {target_path}")

    if common != base_resolved:
        raise SecurityException(f"Path traversal detected: {target_path} escapes jail {base_dir}")

    return target_resolved


@dataclass
class FileState:
    path: str
    sha256: str
    size_bytes: int
    exists: bool


@dataclass
class StateVerificationResult:
    is_valid: bool
    modified_files: List[str]
    unmodified_files: List[str]
    created_files: List[str]
    deleted_files: List[str]
    flags: List[HallucinationFlag]
    pre_hashes: Dict[str, str] = field(default_factory=dict)
    post_hashes: Dict[str, str] = field(default_factory=dict)


class SandboxVerifier:
    """
    Ephemeral sandbox verifier that benchmarks agent filesystem claims
    against cryptographic state diffs.
    """

    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB safety cap per file

    def __init__(self, workspace_path: Optional[str] = None):
        self.workspace_path = workspace_path
        self._temp_dir: Optional[str] = None

    def create_ephemeral_sandbox(self) -> str:
        """Create an isolated temporary sandbox directory with safe directory copy."""
        self._temp_dir = tempfile.mkdtemp(prefix="agenttrace_sandbox_")
        if self.workspace_path and os.path.exists(self.workspace_path):
            safe_workspace = os.path.realpath(self.workspace_path)
            dest_workspace = os.path.join(self._temp_dir, "workspace")
            # Copy without following dangerous external symlinks
            shutil.copytree(safe_workspace, dest_workspace, symlinks=False, dirs_exist_ok=True)
            return dest_workspace
        return self._temp_dir

    def cleanup(self) -> None:
        """Safely destroy the ephemeral sandbox."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None

    @classmethod
    def compute_file_hash(cls, filepath: str) -> Optional[str]:
        """Compute SHA-256 hash of a file with size bounds and symlink checks."""
        if not os.path.isfile(filepath) or os.path.islink(filepath):
            return None
        
        try:
            size = os.path.getsize(filepath)
            if size > cls.MAX_FILE_SIZE_BYTES:
                return None  # Skip unbounded large files to prevent DoS
            
            hasher = hashlib.sha256()
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, PermissionError):
            return None

    def snapshot_state(self, root_dir: str) -> Dict[str, str]:
        """Take a snapshot of all file SHA-256 hashes inside root_dir with jail enforcement."""
        state = {}
        real_root = os.path.realpath(root_dir)

        for root, _, files in os.walk(real_root, followlinks=False):
            for file in files:
                full_path = os.path.join(root, file)
                
                # Check for symlink jail escapes
                if os.path.islink(full_path):
                    continue

                try:
                    assert_safe_path(real_root, full_path)
                except SecurityException:
                    continue

                rel_path = os.path.relpath(full_path, real_root)
                # Ignore git internals or cache
                if ".git" in rel_path or "__pycache__" in rel_path or ".pytest_cache" in rel_path:
                    continue

                sha = self.compute_file_hash(full_path)
                if sha:
                    state[rel_path] = sha

        return state

    def verify_claims_against_state(
        self,
        pre_state: Dict[str, str],
        post_state: Dict[str, str],
        claimed_modified_files: List[str],
        base_dir: Optional[str] = None,
    ) -> StateVerificationResult:
        """
        Compare claimed file modifications against true cryptographic hash deltas.
        Validates claimed paths against directory traversal attacks.
        """
        flags: List[HallucinationFlag] = []

        all_keys: Set[str] = set(pre_state.keys()) | set(post_state.keys())
        modified = []
        created = []
        deleted = []
        unmodified = []

        for f in all_keys:
            in_pre = f in pre_state
            in_post = f in post_state

            if in_pre and not in_post:
                deleted.append(f)
            elif not in_pre and in_post:
                created.append(f)
            elif in_pre and in_post:
                if pre_state[f] != post_state[f]:
                    modified.append(f)
                else:
                    unmodified.append(f)

        # Check for unverified state mutations with path sanitization
        for claimed_file in claimed_modified_files:
            # Check for path traversal attempts in claimed path
            norm_claimed = os.path.normpath(claimed_file).lstrip("/\\")
            if ".." in norm_claimed.split(os.sep):
                flags.append(
                    HallucinationFlag(
                        step_index=0,
                        type=HallucinationType.UNVERIFIED_STATE_MUTATION,
                        severity="CRITICAL",
                        claim=f"Path Traversal Attempt in claim: '{claimed_file}'",
                        ground_truth="Security Jail Violation: Claimed path contains directory traversal escape sequences.",
                        remediation="Sanitize agent path inputs and restrict writes to jail boundaries.",
                    )
                )
                continue

            matched = False
            for real_mod in modified + created:
                if norm_claimed == real_mod or norm_claimed.endswith(real_mod) or real_mod.endswith(norm_claimed):
                    matched = True
                    break

            if not matched:
                flags.append(
                    HallucinationFlag(
                        step_index=0,
                        type=HallucinationType.UNVERIFIED_STATE_MUTATION,
                        severity="CRITICAL",
                        claim=f"Agent claimed modification to '{claimed_file}'",
                        ground_truth="File was NOT mutated. SHA-256 hash unchanged or file does not exist.",
                        remediation="State verification failed. Model reported successful edit with zero disk delta.",
                    )
                )

        is_valid = len(flags) == 0

        return StateVerificationResult(
            is_valid=is_valid,
            modified_files=modified,
            unmodified_files=unmodified,
            created_files=created,
            deleted_files=deleted,
            flags=flags,
            pre_hashes=pre_state,
            post_hashes=post_state,
        )
