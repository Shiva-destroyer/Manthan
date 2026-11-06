"""manthan.core — the shared kernel (EP-0).

Everything the three modules reuse: model access + RAM scheduling, the
calibrated judge, metrics, the OWASP+ATLAS taxonomy, the SQLite store, the
reporter, typed config, and the CLI. Nothing here imports a module.
"""
