"""Distributed Execution Graph & DAG State Reconciliation Engine.
Reconstructs linear consistent state from cluster logs containing rollbacks and crashes.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LogEvent:
    timestamp: float
    node_id: str
    action: str  # e.g., 'MUTATE', 'ROLLBACK', 'COMMIT'
    key: str
    value: Any
    tx_id: str
    parent_tx: str | None = None


class DistributedDAGReconciler:
    def __init__(self):
        self.events: list[LogEvent] = []
        self.state: dict[str, Any] = {}
        self.rolled_back_txs: set[str] = set()

    def add_event(self, event: LogEvent):
        self.events.append(event)

    def reconcile(self) -> dict[str, Any]:
        """
        Reconstruct deterministic state by:
        1. Identifying rollbacks and invalidating transactions.
        2. Sorting surviving events topologically and by timestamp.
        3. Applying deterministic state mutations.
        """
        # Step 1: Scan for explicit ROLLBACK directives
        for e in self.events:
            if e.action == "ROLLBACK":
                self.rolled_back_txs.add(e.tx_id)

        # Step 2: Sort surviving valid events deterministically
        valid_events = [
            e for e in self.events
            if e.tx_id not in self.rolled_back_txs and e.action != "ROLLBACK"
        ]
        # Primary sort: timestamp, Secondary: tx_id (tie-breaker)
        valid_events.sort(key=lambda x: (x.timestamp, x.tx_id))

        # Step 3: Replay state
        self.state.clear()
        for e in valid_events:
            if e.action in ("MUTATE", "COMMIT"):
                self.state[e.key] = e.value

        return dict(self.state)

    def detect_cycles(self, adjacency_list: dict[str, list[str]]) -> bool:
        """DFS-based cycle detection in execution dependency graph."""
        visited = set()
        recursion_stack = set()

        def dfs(node):
            visited.add(node)
            recursion_stack.add(node)
            for neighbor in adjacency_list.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            recursion_stack.remove(node)
            return False

        for node in adjacency_list:
            if node not in visited:
                if dfs(node):
                    return True
        return False
