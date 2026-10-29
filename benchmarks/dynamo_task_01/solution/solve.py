#!/usr/bin/env python3
"""
Oracle Solver for Task: Distributed Event Stream State Reconciliation
Parses chronological events, tracks transaction lifecycle, reconciles out-of-order mutations,
and computes deterministic canonical state with cryptographic SHA-256 verification.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List, Set, Tuple


def reconcile_events(input_path: str, output_path: str) -> Dict[str, Any]:
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input event log not found at: {input_path}")

    events: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    # Phase 1: Track transaction status (commits vs rollbacks)
    rolled_back_txs: Set[str] = set()
    committed_txs: Set[str] = set()
    mutations_by_tx: Dict[str, List[Dict[str, Any]]] = {}

    for ev in events:
        action = ev["action"]
        tx_id = ev["tx_id"]

        if action == "ROLLBACK":
            rolled_back_txs.add(tx_id)
        elif action == "COMMIT":
            committed_txs.add(tx_id)
        elif action == "MUTATE":
            mutations_by_tx.setdefault(tx_id, []).append(ev)

    # Discard any transaction that was rolled back (even if committed earlier)
    valid_txs = committed_txs - rolled_back_txs
    discarded_txs = (set(mutations_by_tx.keys()) | committed_txs | rolled_back_txs) - valid_txs

    # Phase 2: Collect all valid committed mutations
    valid_mutations: List[Dict[str, Any]] = []
    for tx in valid_txs:
        valid_mutations.extend(mutations_by_tx.get(tx, []))

    # Phase 3: Reconcile state per key with causality rules:
    # Highest timestamp wins; if timestamps tie, lexicographical node_id wins
    mutations_per_key: Dict[str, List[Dict[str, Any]]] = {}
    for m in valid_mutations:
        mutations_per_key.setdefault(m["key"], []).append(m)

    final_state: Dict[str, Any] = {}
    for key, candidates in mutations_per_key.items():
        # Sort candidates by (timestamp, node_id) ascending -> last one wins
        candidates.sort(key=lambda x: (float(x["timestamp"]), str(x["node_id"])))
        final_state[key] = candidates[-1]["value"]

    # Phase 4: Compute canonical SHA-256 checksum
    canonical_json = json.dumps(final_state, sort_keys=True, separators=(",", ":"))
    sha256_digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    output_payload = {
        "status": "reconciled",
        "total_events_processed": len(events),
        "committed_transactions": len(valid_txs),
        "discarded_transactions": len(discarded_txs),
        "state": final_state,
        "sha256_checksum": sha256_digest,
    }

    # Ensure parent output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    return output_payload


def main():
    parser = argparse.ArgumentParser(description="Oracle Solver for Distributed Event Reconciliation")
    parser.add_argument("--input", default="/workspace/data/events.jsonl", help="Path to input events.jsonl")
    parser.add_argument("--output", default="/workspace/state_output.json", help="Path to write state_output.json")
    args = parser.parse_args()

    try:
        res = reconcile_events(args.input, args.output)
        print(f"Successfully reconciled {res['total_events_processed']} events into {args.output}")
        print(f"State Checksum: {res['sha256_checksum']}")
    except Exception as e:
        print(f"Solver Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
