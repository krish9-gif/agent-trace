"""Security and sandboxing utilities for containerized test harnesses."""
from pathlib import Path
import os


def assert_safe_path(base_dir: Path | str, target_path: Path | str) -> Path:
    """
    Enforce strict path containment to prevent path traversal attacks (e.g., ../../etc/passwd).
    Ensures that target_path strictly resolves within base_dir.
    """
    base = Path(base_dir).resolve()
    target = Path(target_path).resolve()

    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(
            f"Security Violation: Target path '{target}' escapes allowed base sandbox '{base}'"
        )
    return target


def check_resource_limits() -> dict[str, str]:
    """Inspect environment sandbox limits (memory cgroup / quota if available)."""
    limits = {
        "sandbox_type": "container" if os.path.exists("/.dockerenv") else "host",
        "cpu_count": str(os.cpu_count() or 1),
    }
    cgroup_mem = Path("/sys/fs/cgroup/memory.max")
    if cgroup_mem.exists():
        try:
            limits["cgroup_memory_max"] = cgroup_mem.read_text().strip()
        except Exception:
            limits["cgroup_memory_max"] = "unavailable"
    return limits
