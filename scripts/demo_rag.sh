#!/usr/bin/env bash
# Demo: RAG poisoning curve (N=1..5) then the 4-layer defense stack collapsing it.
set -euo pipefail
export MANTHAN_BACKEND="${MANTHAN_BACKEND:-ollama}"
manthan run rag --config configs/manthan.yaml
echo "ASR-vs-N and defense efficacy in the HTML report under data/results/."
