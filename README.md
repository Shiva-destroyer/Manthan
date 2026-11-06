<div align="center">

<img src="assets/icon.svg" width="112" alt="Manthan logo"/>

# Manthan

**Churn the model, find the poison.**

Offline AI red teaming for prompt injection, RAG poisoning and agent attacks,<br/>
run end to end on a CPU-only laptop.

[![CI](https://github.com/Shiva-destroyer/Manthan/actions/workflows/ci.yml/badge.svg)](https://github.com/Shiva-destroyer/Manthan/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Models](https://img.shields.io/badge/models-local%20via%20Ollama-lightgrey)
![GPU](https://img.shields.io/badge/GPU-not%20needed-lightgrey)

**[Watch](#watch-it) · [Labs](#the-three-labs) · [Results](#what-i-found) · [How it works](#how-it-works) · [Quickstart](#quickstart) · [Questions](#questions-people-ask) · [Docs](#docs)**

</div>

<br/>

![The web UI replays a real stored attack: attacker, target, guard and the two judges, with the judges' verdict ATTACK WORKED.](docs/media/readme-hero.png)

> [!IMPORTANT]
> Manthan attacks only local open models and the test apps in this repo. Every secret, key and
> personal detail in it is fake. Read [SECURITY.md](SECURITY.md) before you run it.

## In one minute

AI chatbots and agents follow orders written in plain words. So an attacker can use plain words too,
and talk them out of their rules. Security teams find weak spots by attacking their own systems
first. That is red teaming. I built Manthan to do the same for AI models, on my own laptop.

Manthan runs three kinds of attack against small local models. One model plays the attacker, and
judge models score every reply. Manthan then counts how often the attacks work, and how often a
defence stops them. Every number below comes from two full stored runs and the judge calibration file.

- Chat attacks made the target leak a fake secret in **20 of 60** tries.
- A guard model stopped **18 of the 20** attacks that had worked. Not all of them.
- Poisoned documents fooled the RAG app in **100%** of answers with four or more poison files.
  With all four defence layers on, **0%** of answers were poisoned, but two of those layers are best-case.
- No agent attack sent the fake key out (**0 of 10** for each attack). That does not prove the agent is safe.
- My judge raised too many false alarms: **19%** against a **15%** goal. The limits are listed below.

## Watch it

**Pitch.** One attack, one guard, the headline numbers.

https://github.com/user-attachments/assets/a18f4730-3f2f-47ae-8882-cbf36535418b

<details>
<summary><b>Two more videos: the demo and the explainer</b></summary>

<br/>

**Demo.** Three ways to attack an AI, one real run from each lab.

https://github.com/user-attachments/assets/fd72c728-bd28-4ddc-928e-a14b790ce28c

**Explainer.** How I scored the attacks, and what the numbers cannot show.

https://github.com/user-attachments/assets/63152a1b-6daa-4281-ae93-6333648c6d80

</details>

All three are also in the [v1.0.0 release](https://github.com/Shiva-destroyer/Manthan/releases/tag/v1.0.0) to download.

## The three labs

Each AI attack has an older security twin. If you know the classic attack, you already know the idea.

| Lab | Classic security twin | What the attack does here | Defence I tested |
|---|---|---|---|
| **Prompt** | SQL injection: data turns into commands | An attacker model plays a locked-out customer and talks the target into leaking a recovery code | A guard model that screens every message first |
| **RAG** | Supply-chain attack: a bad part in something you trust | Poisoned files in the documents the model searches change its answer | Four layers: retrieval filter, guard, context separation, output check |
| **Agent** | Phishing: an email that tricks a person into acting | Hidden orders in an inbox email or a tool description tell the agent to send a fake key out | A tool-description scan and a runtime monitor, inside a closed test network |

## What I found

Two full campaigns ran on 2026-11-04, with seeds 1337 and 7331. They took 214 and 212 minutes.
A range is the Wilson 95% interval: where the true rate likely sits, given the small sample.
Details are in [docs/results.md](docs/results.md).

| Lab | What I measured | Result |
|---|---|---|
| Prompt | Attacks that made the target leak its secret | 20 of 60 (range 23% to 46%) |
| Prompt | Crescendo / TAP attack strategies | 8 of 30 (14 to 44%) / 12 of 30 (25 to 58%) |
| Prompt | Guard model: of the attacks that worked on the plain target, the guarded copy failed in | 18 of 20 (range 70% to 97%) |
| RAG | Poisoned answers with 0 / 1 / 2 / 3 / 4 / 5 poison files (per run) | 0% / 33% / 47% and 53% / 47% and 50% / 100% / 100% |
| RAG | Poisoned answers with all four defence layers on | 0% in both runs |
| Agent | Attacks that sent the fake key out, for each of the five attacks | 0 of 10 |
| Judge | False alarms of the rubric judge on 48 held-out replies | 19% (goal 15%, not met) |

### Limits

Please read these with the numbers above.

- The judge misses its own goal. It raised false alarms on 19% of the replies that were not real wins,
  against a 15% goal, on 48 held-out replies.
- A campaign win also needs the secret marker in the reply. So the 19% does not carry over to the
  campaign rates one to one. [docs/methodology.md](docs/methodology.md) explains why.
- The samples are small: two runs, 15 attempts per strategy per run, one target model, one laptop.
  The Crescendo and TAP ranges overlap, so these runs do not show which strategy is stronger.
- The guard stopped 18 of the 20 attacks that worked without it. Not all of them.
- Two of the four RAG defences are best-case. One knows the poison source, and one knows the clean
  answer. Real systems do not get this for free.
- No agent attack worked in these runs. That does not prove the agent is safe. The agent read the fake
  key in one demo run, but it never sent it.
- The agent lab uses fake MCP tool servers and a fake attacker server on a closed Docker network.
- A human checked a random sample of 20 of the reference labels and agreed with all 20.

## How it works

```mermaid
flowchart LR
    A[Attacker model] -->|attack message| T[Target model or app]
    T -->|reply| J[Judges]
    J -->|verdict| S[(SQLite store)]
    S --> R[HTML report]
    S --> U[Web UI]
    G[Guard model] -.->|defence| T
```

Each lab runs the same loop: make an attack, run it on the target, let the judges score the reply,
tag it with OWASP and MITRE ATLAS ids, and store it. The report and the web UI read the store.

**How a win is decided.** Two judges read every reply. One is a fixed rule check for the secret
marker and for refusal phrases. The other is a rubric judge (`phi4-mini`). They vote, and a tie goes
to the more confident side. A reply without the secret marker can never count as a success.
A judge is like an intrusion detector: it can raise false alarms, so I measured how often it does.

**What runs where.** Every model runs on the laptop through [Ollama](https://ollama.com):

| Role | Model |
|---|---|
| Target and agent | `qwen2.5:7b` |
| Attacker | `llama3.2:3b` |
| Judge | `phi4-mini` |
| Embeddings (RAG) | `nomic-embed-text` |
| Guard | `protectai/deberta-v3-base-prompt-injection-v2` (Hugging Face) |

The test laptop has an i7-1360P, 24 GB RAM and no GPU. A scheduler loads and unloads the models so
they fit in RAM. The peak in a full run was 18.0 GB. More in [docs/architecture.md](docs/architecture.md).

## See it in the UI

![The web UI replays a stored attack: the leaking reply, then the judges mark the run as a win.](docs/media/readme-lab.gif)

| | |
|---|---|
| ![Home page](docs/media/home.png) | ![Agent lab page](docs/media/lab-agent.png) |
| ![RAG lab page](docs/media/lab-rag.png) | ![Results page](docs/media/results.png) |

## Quickstart

This needs Python 3.11. The mock backend needs no models and no network.

```bash
git clone https://github.com/Shiva-destroyer/Manthan.git
cd Manthan
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export MANTHAN_BACKEND=mock     # configs/models.yaml defaults to ollama
manthan verify-taxonomy         # check the OWASP and ATLAS ids
manthan run all --smoke         # a short campaign in all three labs
pytest -m "not local_only"      # the CI test set, with sockets off
```

The mock backend gives fake replies, so its numbers mean nothing. It only proves the pipeline works.

<details>
<summary><b>Real local run with Ollama</b></summary>

<br/>

Install Ollama, pull the models, then run with the real backend. The full steps, with RAM notes and
troubleshooting, are in [docs/running-locally.md](docs/running-locally.md).

```bash
pip install -e '.[local,dev]'
ollama pull qwen2.5:7b
ollama pull llama3.2:3b
ollama pull phi4-mini
ollama pull nomic-embed-text
export MANTHAN_BACKEND=ollama
manthan run all --config configs/manthan.yaml
```

</details>

<details>
<summary><b>Web UI</b></summary>

<br/>

It shows the labs, the results and the judge numbers. It listens on `127.0.0.1` only.

```bash
pip install -e '.[ui]'
manthan ui                      # then open http://127.0.0.1:8765
```

</details>

## Questions people ask

<details>
<summary><b>Why run everything locally on a CPU?</b></summary>

<br/>

I wanted to show that useful red teaming does not need a GPU or a cloud account. Local models also
mean that no paid API is called and no real data leaves the laptop. After the one-time model
download, a full campaign runs offline.

</details>

<details>
<summary><b>Does the guard solve prompt injection?</b></summary>

<br/>

No. Of the 20 attacks that worked on the plain target, the guarded copy failed in 18. The other 2
still worked behind the guard. Attacks that failed on the plain target were not run again with the guard. The demo video shows one: a softer question about a general
process, which the guard let through.

</details>

<details>
<summary><b>Can I trust the judge?</b></summary>

<br/>

Only with care. I tested it on 48 held-out replies with known labels. It caught 5 of 5 real wins,
but it raised a false alarm on 8 of the 43 others (19%). In a campaign, a win also needs the secret
marker in the reply, which limits these false alarms. I did not measure the campaign false-alarm
rate itself. [docs/methodology.md](docs/methodology.md) has the full check.

</details>

<details>
<summary><b>No agent attack worked. Is the agent safe?</b></summary>

<br/>

No. With 0 of 10 tries, the range still goes up to 28%. A small model may also fail to follow
hidden orders at all. In one demo run the agent read the fake key file, but it never sent it.

</details>

<details>
<summary><b>Why does garak report 60% and 47%, but Manthan 0%?</b></summary>

<br/>

They answer different questions about the same replies. garak scores its probes with its own
detectors. Manthan rescored those replies with its judges, which look only for the leaked secret.

</details>

<details>
<summary><b>Is this new research?</b></summary>

<br/>

No. Manthan reproduces known, published attack types, such as Crescendo, TAP, RAG poisoning and
MCP tool attacks. It measures them and the defences against them, on a small laptop budget.

</details>

## Under the hood

<details>
<summary><b>Attacks, defences and detectors in each lab</b></summary>

<br/>

| Lab | Attacks | Defences and detectors |
|---|---|---|
| Prompt | Crescendo (slow multi-turn push), TAP (a tree of attack ideas, pruned), leetspeak and base64 tricks, and an optional garak baseline | A guard model in front of the target |
| RAG | Poisoned files, keyword-stuffed decoys, prompt-leak and fake-PII probes | Four layers: retrieval filter, prompt guard, context separation, output check |
| Agent | Hidden orders in an inbox message or a tool description, a tool that changes after approval, a fake tool with a real tool's name, an over-powered command tool | A static scan of tool descriptions and a runtime monitor |

</details>

<details>
<summary><b>Framework mapping (OWASP and MITRE ATLAS)</b></summary>

<br/>

These are only the ids the code maps. `manthan verify-taxonomy` checks them.

| Lab | OWASP (LLM Top 10 2025, Agentic) | MITRE ATLAS |
|---|---|---|
| Prompt | LLM01, LLM02, LLM07 | AML.T0051.000, AML.T0051.001, AML.T0054, AML.T0057, AML.T0065, AML.T0068 |
| Agent | LLM06, ASI01, ASI02 | AML.T0051.001, AML.T0053, AML.T0086, AML.T0110 |
| RAG | LLM02, LLM04, LLM07, LLM08 | AML.T0051.001, AML.T0057, AML.T0066, AML.T0070 |

</details>

## Docs

| Doc | What is in it |
|---|---|
| [Overview](docs/overview.md) | The idea in plain words, no code |
| [Architecture](docs/architecture.md) | The core, the labs, the store and the UI |
| [Methodology](docs/methodology.md) | The attacks, the judges and the statistics |
| [Results](docs/results.md) | The two runs in detail |
| [Running locally](docs/running-locally.md) | Setup, real runs and troubleshooting |
| [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Changelog](CHANGELOG.md) | Rules of use, checks, versions |

## Credits

- Models: `qwen2.5:7b`, `llama3.2:3b`, `phi4-mini`, `nomic-embed-text` and
  `protectai/deberta-v3-base-prompt-injection-v2`. Each has its own license.
- Baseline scanner: [garak](https://github.com/NVIDIA/garak).
- Video voice: Piper en_US-ryan-high (RyanSpeech dataset, CC BY-NC-SA 4.0).
- Fonts in the web UI: Gelasio, IBM Plex Sans and JetBrains Mono, under the SIL Open Font License.

## License and author

Apache-2.0. See [LICENSE](LICENSE). Model weights are not in this repo. You pull them yourself.

Made by **Sai Srujan** · [GitHub](https://github.com/Shiva-destroyer) · [LinkedIn](https://www.linkedin.com/in/sai-srujan-murthy-bb6801322) · [Email](mailto:saisrujanmurthy@gmail.com)
