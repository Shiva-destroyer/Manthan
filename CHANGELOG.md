# Changelog

## 1.0.0

First public release.

- One shared core: model backends and the model-slot scheduler, judges, metrics with Wilson ranges,
  OWASP and MITRE ATLAS tags, a SQLite store and an HTML report.
- Three labs: prompt attacks (Crescendo, TAP, garak baseline), RAG poisoning with four defence
  layers, and an agent lab with MCP tool attacks in a closed Docker network.
- A judge calibration on 88 labeled replies, stored in `src/manthan/core/calibration`.
- A local web UI (`manthan ui`) to browse labs, results and judge numbers.
- Results of two full campaigns in [docs/results.md](docs/results.md).
