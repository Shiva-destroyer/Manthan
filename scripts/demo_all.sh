#!/usr/bin/env bash
# Demo: one unified campaign across all three domains -> one report + heatmap.
set -euo pipefail
export MANTHAN_BACKEND="${MANTHAN_BACKEND:-mock}"
manthan run all --smoke --config configs/manthan.yaml
echo "Unified cross-domain report (OWASP x ATLAS heatmap) under data/results/."
