# Task: Distributed Event Stream State Reconciliation

## Overview
You are provided with a chronological log of distributed transactions emitted by multi-region nodes in `/workspace/data/events.jsonl`.
The stream contains state mutations, atomic transaction commits, and explicit transaction rollbacks. Due to network partitioning, events may arrive out of order, and rolled-back transactions must not be reflected in the final state.

Your objective is to reconcile the event log and produce the final deterministic key-value state and its cryptographic integrity checksum in `/workspace/state_output.json`.

---

## Input Specification
The input file is located at `/workspace/data/events.jsonl`. Each line is a JSON object with the following schema:

```json
{
  "timestamp": <float>,
  "node_id": "<str>",
  "action": "<MUTATE | ROLLBACK | COMMIT>",
  "tx_id": "<str>",
  "key": "<str>",
  "value": <int | str | null>
}
```

### Event Processing Rules:
1. **Transaction Lifecycle**:
   - A transaction `tx_id` can contain multiple `MUTATE` actions.
   - If a transaction has a `ROLLBACK` event, all mutations associated with that `tx_id` must be completely discarded, regardless of when the rollback appears in the log.
   - Only mutations belonging to transactions with a `COMMIT` event (and zero `ROLLBACK` events) are valid candidates for final state.
2. **Causality & Ordering**:
   - For valid committed mutations targeting the same `key`, the mutation with the highest `timestamp` determines the final value.
   - If two valid mutations for the same `key` have identical timestamps, the event with lexicographically greater `node_id` takes precedence.

---

## Output Contract
You must write the final resolved state to `/workspace/state_output.json`.
The output must be formatted as follows:

```json
{
  "status": "reconciled",
  "total_events_processed": <int>,
  "committed_transactions": <int>,
  "discarded_transactions": <int>,
  "state": {
    "<key>": <final_value>
  },
  "sha256_checksum": "<hex_digest>"
}
```

### Checksum Computation:
`sha256_checksum` must be the SHA-256 hex digest of the canonical JSON string of the `"state"` dictionary (sorted keys, compact separators `","` and `":"`, UTF-8 encoded).

---

## Constraints
- All file operations must occur within `/workspace`.
- Output file `/workspace/state_output.json` must be strictly valid JSON.
- Tests will assert exact key-value states and cryptographic checksum match.
