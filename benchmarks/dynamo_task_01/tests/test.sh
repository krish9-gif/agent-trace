#!/usr/bin/env bash
# Deterministic offline test runner script
set -euo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${TEST_DIR}/..:${PYTHONPATH:-}"

echo "[EVAL_RUNNER] Initiating offline PyTest suite..."
python3 -m pytest "${TEST_DIR}/test_outputs.py" -v --tb=short
