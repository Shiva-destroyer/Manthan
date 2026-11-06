# Contributing

Thank you for looking. This is a small student project, so please keep changes small and focused.

## Scope

- Attacks run only against local models and the test apps in this repo. See [SECURITY.md](SECURITY.md).
- Secrets and personal data must be fake and clearly marked.
- New numbers in the docs need a source: a stored run, a test or a file in the repo.

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export MANTHAN_BACKEND=mock
```

## Checks to run before a pull request

These are the same checks CI runs:

```bash
ruff check src tests
black --check src tests
mypy
manthan verify-taxonomy
pytest -m "not local_only" --cov=manthan.core --cov-fail-under=85
manthan run all --smoke
```

If you change the web UI (`src/manthan/ui/web`):

```bash
cd src/manthan/ui/web
npm ci
npm run check
npm run build      # writes the bundle to src/manthan/ui/static
```

Tests that need real models are marked `local_only`. See [docs/running-locally.md](docs/running-locally.md).

## Style

- Python 3.11, formatted with black and checked with ruff and mypy.
- `pre-commit install` sets up the same hooks locally.
- One purpose per pull request. Add or update a test for any behaviour change.
