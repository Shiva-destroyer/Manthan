#!/usr/bin/env bash
# Demo: adaptive prompt fuzzing vs a local target + DefendedTarget, calibrated judge.
# Local run (needs Ollama). For an offline dry-run, prefix with MANTHAN_BACKEND=mock.
set -euo pipefail
export MANTHAN_BACKEND="${MANTHAN_BACKEND:-ollama}"
manthan verify-taxonomy
manthan run prompt --config configs/manthan.yaml
manthan calibrate
echo "Open the HTML report under data/results/."
