"""Common Test Report Format (CTRF) Schema Reporter."""
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Literal


@dataclass
class CTRFTest:
    name: str
    status: Literal["passed", "failed", "skipped", "pending", "other"]
    duration: float
    message: str | None = None
    trace: str | None = None


@dataclass
class CTRFReport:
    report_format: str = "CTRF"
    version: str = "0.0.1"
    tool_name: str = "deterministic-eval-harness"
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    summary: dict = field(default_factory=dict)
    tests: list[dict] = field(default_factory=list)

    def add_test(self, test: CTRFTest):
        self.tests.append(asdict(test))

    def finalize(self) -> dict:
        passed = sum(1 for t in self.tests if t["status"] == "passed")
        failed = sum(1 for t in self.tests if t["status"] == "failed")
        skipped = sum(1 for t in self.tests if t["status"] == "skipped")
        self.summary = {
            "tests": len(self.tests),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "pending": 0,
            "other": 0,
            "start": self.timestamp,
            "stop": int(time.time() * 1000),
        }
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.finalize(), indent=indent)
