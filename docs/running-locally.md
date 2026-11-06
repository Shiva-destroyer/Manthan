# Running locally

CI runs everything on the mock backend, with no models and no network. This page is for running the
real local models on your own machine: real campaigns, the `local_only` tests and the demos.

After the one-time downloads below, every command here runs offline on the CPU. No paid API is
called. A budget guard refuses any non-local backend unless you set
`budget.allow_non_local_backend: true`. You never need to.

## 0. The test machine

I ran the results in [results.md](results.md) on this laptop:

- CPU: Intel Core i7-1360P. GPU: Intel Iris Xe, not used (CPU-only inference).
- RAM: 24 GB. The peak in a full run was 18.0 GB.
- OS: Arch Linux. Runtime: Ollama, Python 3.11, Docker.

CPU-only inference is slow and limited by memory. The model-slot scheduler loads only the models
each phase needs, and it stops rather than swaps if a phase would not fit in RAM.

## 1. One-time setup

### 1a. Python (3.11 only)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install -e '.[local,ui,dev]'   # agent + rag + guard + ollama + dashboard, the web UI, dev tools
```

`requirements.lock` is a pip freeze of a CI-like environment (core and dev extras). CI installs from `pyproject.toml`, not from the lock. The heavy local extras are pinned as ranges
in `pyproject.toml`.

`garak` and the MCP scanner clash with these pins, so they are not in `local`. Both are optional:

- **garak**: install it in its own virtual environment. Set `prompt.garak_enabled: true` and
  `prompt.garak_bin` (the path to its `garak` command) in your config.
- **MCP scanner**: without it, the agent lab uses its built-in description scan.

### 1b. Pull the models (you run these; Manthan never downloads models)

```bash
ollama pull qwen2.5:7b        # target and agent
ollama pull llama3.2:3b       # attacker
ollama pull phi4-mini         # judge
ollama pull nomic-embed-text  # embeddings (RAG)
ollama pull llama3.1:8b       # optional: another RAG generator
```

`manthan models pull` prints these commands. `manthan models status` prints the residency plan and
a RAM check.

### 1c. The guard model

The default guard is `protectai/deberta-v3-base-prompt-injection-v2` (not gated, about 440 MB).
It downloads into your Hugging Face cache on first use. To fetch it ahead of time:

```bash
python - <<'PY'
from transformers import pipeline
pipeline("text-classification", model="protectai/deberta-v3-base-prompt-injection-v2")
PY
```

Optional gated guard: Llama Prompt Guard 2 (`meta-llama/Llama-Prompt-Guard-2-86M`). Accept its license
on Hugging Face, set `HF_TOKEN`, then set `guard.kind: prompt-guard-2` in `configs/models.yaml`.

Optional low-RAM guard: the ONNX Runtime path avoids loading full PyTorch for the guard.

```bash
pip install -e '.[guard-onnx]'
# then in configs/models.yaml:  guard: { use_onnx: true }
```

## 2. Environment variables

`configs/models.yaml` defaults to the Ollama backend. Set these before a real run:

```bash
export MANTHAN_BACKEND=ollama
export OLLAMA_NUM_PARALLEL=1           # one request at a time (CPU-bound)
export OLLAMA_MAX_LOADED_MODELS=2      # sequential mode: at most two models loaded
export OLLAMA_KEEP_ALIVE=5m            # unload idle models after 5 minutes
```

Residency modes (`residency.mode` in `configs/models.yaml`):

- **`sequential`** (default): generation holds the attacker and the target. Judging unloads the
  attacker and loads the judge.
- **`concurrent-fast`** (opt-in): keeps attacker, target and judge loaded. Set
  `OLLAMA_MAX_LOADED_MODELS=3`. The scheduler refuses to start with less than 11 GB free.

## 3. Real campaigns

```bash
manthan models status                       # residency plan and RAM check
manthan verify-taxonomy                     # check the OWASP and ATLAS ids
manthan run prompt --config configs/manthan.yaml
manthan run rag    --config configs/manthan.yaml
manthan run agent  --config configs/manthan.yaml   # simulated lab unless agent.lab is docker
manthan run all    --config configs/manthan.yaml   # all three labs, one report
manthan run all --skip agent --verbose            # leave a lab out; one DEBUG line per run
manthan report --campaign <id>              # render the report again for one campaign
manthan calibrate --labeled src/manthan/core/calibration/labeled_set_real.jsonl --split test
```

- `--skip <lab>` can repeat. The run manifest records it.
- `--seed <int>` sets the seed. `--log-json` writes one JSON object per log line.
- `calibrate --labeled ... --split test` scores the judges on the 48 held-out replies of the labeled
  set. The judges never see the marker during calibration.

Results go to `data/results/manthan.db`, with an HTML and a Markdown report next to it.

### Repeat the two published runs

The runs in [results.md](results.md) used `configs/manthan.yaml` with four changes:

```yaml
seed: 1337                 # run 2 used 7331
prompt:  { n_trials: 3, garak_enabled: true }
agent:   { lab: docker }
rag:     { attack: { n_poison_min: 0 } }
```

Expect your numbers to differ. The two published runs also differ from each other.

## 4. The web UI

```bash
manthan ui                                   # http://127.0.0.1:8765
manthan ui --db data/results/manthan.db      # browse a results database, read-only
manthan ui --calibration src/manthan/core/calibration/judge_calibration_real.json
```

It binds `127.0.0.1` only, and there is no `--host` option. `--db` and `--calibration` can repeat.
There is also a Streamlit dashboard: `manthan dashboard`.

## 5. The live agent lab (Docker, acceptance test AT-A4)

The lab runs `ollama`, `agent`, `mcp-legit`, `mcp-malicious` and `mock-exfil` on a Docker network
marked `internal: true`. It has no route to the internet. The only place the agent can send data is
the `mock-exfil` listener, which logs attempts and stores nothing real.

```bash
docker compose -f src/manthan/modules/agent/docker-compose.yml build    # once, needs network
docker compose -f src/manthan/modules/agent/docker-compose.yml up -d --no-build --pull never
# ... run with agent.lab: docker ...
docker compose -f src/manthan/modules/agent/docker-compose.yml down
```

## 6. Local-only tests

These tests are skipped in CI. They need live Ollama, and the agent ones need the Docker lab.

```bash
export MANTHAN_BACKEND=ollama OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=2
pytest -m local_only tests/prompt/test_prompt_integration.py -v
pytest -m local_only tests/rag/test_rag_integration.py -v
pytest -m local_only tests/agent/test_detection.py -v        # with the Docker lab up
pytest -m local_only -v                                       # all of them
```

## 7. Demo scripts and fixtures

```bash
scripts/demo_prompt.sh     # prompt attacks and the judges
scripts/demo_agent.sh      # the agent lab
scripts/demo_rag.sh        # the RAG poisoning curve and the defences
scripts/demo_all.sh        # one campaign across all three labs
```

CI replays recorded model replies, so it needs no model and no network. To record them again from
your local models:

```bash
export MANTHAN_BACKEND=ollama
python scripts/record_fixtures.py     # writes tests/fixtures/*
```

## 8. Troubleshooting

- **The scheduler stops with a RAM message.** It is protecting your machine from swap. Close other
  apps, keep `residency.mode: sequential`, or use the ONNX guard.
- **`concurrent-fast` is refused.** You have less than 11 GB free. Use `sequential`.
- **The first model call is slow.** The model is loading into RAM. Later calls reuse it until
  `OLLAMA_KEEP_ALIVE` runs out.
- **The guard download fails.** The guard is not gated. Check your network for the one-time
  Hugging Face download. After that, everything runs offline.
