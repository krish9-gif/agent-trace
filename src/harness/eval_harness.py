"""Two-tier deterministic evaluation harness runner.
Separates fast 2-second smoke checks from exhaustive verification suites.
"""
from pathlib import Path
import time
from typing import Callable, Any
from .security import assert_safe_path
from .ctrf_reporter import CTRFReport, CTRFTest


class TwoTierEvalHarness:
    def __init__(self, sandbox_root: Path | str):
        self.sandbox_root = Path(sandbox_root).resolve()
        self.smoke_checks: list[tuple[str, Callable[[], bool]]] = []
        self.deep_checks: list[tuple[str, Callable[[], bool]]] = []
        self.report = CTRFReport()

    def register_smoke(self, name: str, fn: Callable[[], bool]):
        """Register a fast (< 2s) smoke probe check."""
        self.smoke_checks.append((name, fn))

    def register_deep(self, name: str, fn: Callable[[], bool]):
        """Register an exhaustive verification assertion."""
        self.deep_checks.append((name, fn))

    def run(self) -> dict[str, Any]:
        """Execute the two-tier evaluation."""
        # 1. Tier 1: Smoke Probes
        smoke_passed = True
        for name, fn in self.smoke_checks:
            t0 = time.time()
            try:
                ok = fn()
                dur = round((time.time() - t0) * 1000, 2)
                if ok:
                    self.report.add_test(CTRFTest(name=f"smoke::{name}", status="passed", duration=dur))
                else:
                    smoke_passed = False
                    self.report.add_test(CTRFTest(name=f"smoke::{name}", status="failed", duration=dur, message="Smoke invariant failed"))
                    break
            except Exception as e:
                smoke_passed = False
                dur = round((time.time() - t0) * 1000, 2)
                self.report.add_test(CTRFTest(name=f"smoke::{name}", status="failed", duration=dur, message=str(e)))
                break

        # If smoke failed, abort deep checks early to save compute
        if not smoke_passed:
            return {
                "tier": "smoke_failed",
                "success": False,
                "report": self.report.finalize()
            }

        # 2. Tier 2: Deep Verification
        all_passed = True
        for name, fn in self.deep_checks:
            t0 = time.time()
            try:
                ok = fn()
                dur = round((time.time() - t0) * 1000, 2)
                if ok:
                    self.report.add_test(CTRFTest(name=f"deep::{name}", status="passed", duration=dur))
                else:
                    all_passed = False
                    self.report.add_test(CTRFTest(name=f"deep::{name}", status="failed", duration=dur, message="Assertion failed"))
            except Exception as e:
                all_passed = False
                dur = round((time.time() - t0) * 1000, 2)
                self.report.add_test(CTRFTest(name=f"deep::{name}", status="failed", duration=dur, message=str(e)))

        return {
            "tier": "completed",
            "success": all_passed,
            "report": self.report.finalize()
        }
