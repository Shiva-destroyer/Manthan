#!/usr/bin/env bash
# Demo: sandboxed agent/MCP exploitation arc (benign -> pwned -> detected).
# Under the mock backend this runs the SimulatedLab (no Docker). The live
# egress-restricted DockerLab is documented in docs/running-locally.md (AT-A4).
set -euo pipefail
export MANTHAN_BACKEND="${MANTHAN_BACKEND:-mock}"
manthan run agent --config configs/manthan.yaml
echo "Trajectory + detection in the HTML report under data/results/."
