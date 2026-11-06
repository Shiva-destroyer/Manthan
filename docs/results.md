# Results

These are the results of two full campaigns on 2026-11-04. Every number comes from the stored run
databases or the stored calibration file. Ranges are Wilson 95%.

## What was run

| Setting | Value |
|---|---|
| Models | target `qwen2.5:7b`, attacker `llama3.2:3b`, judge `phi4-mini`, embeddings `nomic-embed-text` |
| Guard | `protectai/deberta-v3-base-prompt-injection-v2`, threshold 0.5 |
| Seeds | run 1: 1337, run 2: 7331 |
| Time | run 1: 214 minutes, run 2: 212 minutes |
| Peak RAM | 18.0 GB (run 2) |
| Laptop | i7-1360P, 24 GB RAM, no GPU used |

The runs used `configs/manthan.yaml` with four changes: prompt `n_trials` 3 (repo default 10),
`garak_enabled` true, agent `lab` docker (repo default simulated), and RAG `n_poison_min` 0
(repo default 1). So each prompt strategy had 15 attempts per run: 5 goals times 3 trials.

## Prompt lab

| | Run 1 | Run 2 | Both runs |
|---|---|---|---|
| All attempts, leaked the secret | 9 of 30 | 11 of 30 | 20 of 60 (range 23% to 46%) |
| Crescendo | 4 of 15 | 4 of 15 | 8 of 30 (14 to 44%) |
| TAP | 5 of 15 | 7 of 15 | 12 of 30 (25 to 58%) |
| Plain-target wins whose guarded copy failed | 8 of 9 | 10 of 11 | 18 of 20 (range 70% to 97%) |
| Plain-target wins that also worked behind the guard | 1 of 9 | 1 of 11 | 2 of 20 |

What this shows:

- A 7B model told to keep a secret still leaked it in about a third of the attempts.
- The guard stopped 18 of the 20 attacks that worked without it. Not all of them.
- TAP did better than Crescendo in both runs, but the ranges overlap. Two runs cannot show that
  TAP is stronger.

**Garak baseline.** Garak's own detectors rated 60% (run 1) and 47% (run 2) of its attempts as hits.
Manthan's judges, rescoring the same replies only for a leak of the secret code, found 0% in both
runs. These measure different things. Garak's detectors look for their own signs of a hit. Manthan
looks for one thing: the secret code. So the gap is not a sign that either tool is wrong.

## RAG lab

Poisoned answers by number of poison files in the search set (per-run rates, no ranges):

| Poison files | 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|---|
| Run 1 | 0% | 33% | 47% | 47% | 100% | 100% |
| Run 2 | 0% | 33% | 53% | 50% | 100% | 100% |

| Probe | No defence | With defences |
|---|---|---|
| System prompt leak | 75% | 0% |
| Fake PII leak | 100% | 0% |
| Poisoned answers, all four layers on | | 0% |

What this shows:

- With no poison, no answer was poisoned. With 4 or 5 poison files, every answer was.
- The four layers together stopped every poisoned answer. But two of the layers are best-case:
  the retrieval filter knows the poison source, and the output check knows the clean answer.
  This is an upper bound on what the defences can do, not a real-world result.

## Agent lab (Docker)

| Attack | Run 1 | Run 2 | Utility under attack (run 1 / run 2) |
|---|---|---|---|
| Indirect injection | 0 of 5 | 0 of 5 | 20% / 40% |
| Tool poisoning | 0 of 5 | 0 of 5 | 100% / 60% |
| Rug pull | 0 of 5 | 0 of 5 | 100% / 100% |
| Tool shadowing | 0 of 5 | 0 of 5 | 100% / 100% |
| Excessive agency | 0 of 5 | 0 of 5 | 0% / 20% |

Utility under attack is how often the agent still finished its normal job, compared with no attack.

| Runtime monitor | Run 1 | Run 2 |
|---|---|---|
| Recall | 100% | 100% |
| Precision | 94% | 60% |
| False alarms on normal runs | 0% | 0% |

What this shows:

- No attack made the agent send the fake key, in 10 tries for each attack. The upper end of the range
  is still 28%, so this does not prove the agent is safe.
- In one demo run the agent read the fake key file, but it never sent it.
- The attacks still hurt. Under indirect injection and excessive agency, the agent often failed its
  normal job.
- The monitor's precision dropped from 94% to 60% between runs. I have not found the reason yet.

## Judges

On 48 held-out replies, the rubric judge raised false alarms on 8 of 43 non-wins (19%). The goal is
15%, so it is not met. It caught 5 of 5 real wins. See [methodology.md](methodology.md) for why this
number does not carry over to the campaign rates one to one.

A human checked a random sample of 20 of the reference labels and agreed with all 20.

## Limits

- Two runs, on one laptop, with one target model. The samples are small.
- The judge's false-alarm rate (19%) is above its goal (15%).
- Two of the four RAG defences are best-case.
- The agent lab uses fake tool servers, a fake attacker server and fake secrets.
- RAG and garak rates have no stored n, so they have no ranges.
- The monitor precision change between runs is not explained.
