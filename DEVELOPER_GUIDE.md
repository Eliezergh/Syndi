# Developer Guide

This guide covers the local development workflow for Syndi, including environment setup, linting, formatting, testing, and contribution expectations.

## Prerequisites

- macOS 11 or newer
- Python 3.11+
- A virtual environment tool such as `venv`

## Local Setup

```bash
git clone https://github.com/eliezergh/Syndi.git
cd Syndi

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

To run the app locally:

```bash
python src/syndi.py
```

## Code Quality Checks

Run linting:

```bash
ruff check src tests
```

Check formatting:

```bash
ruff format --check src tests
```

Apply formatting:

```bash
ruff format src tests
```

## Test Suite

Run the full test suite:

```bash
pytest tests -q
```

Run tests with coverage output similar to CI:

```bash
coverage run -m pytest tests/ -v --tb=short
coverage report --fail-under=60
coverage xml
```

## Build Verification

If your change affects packaging or app startup, also verify the bundle build:

```bash
cd setup
python setup.py py2app
```

The built app is generated at `setup/dist/Syndi.app`.

## CI Workflows

The repository currently uses these checks in GitHub Actions:

- `tests.yml`: Ruff lint, Ruff format check, and pytest with coverage
- `build-release.yml`: release gating, macOS app build, ZIP artifact creation, and GitHub release publication
- `codeql.yml`: baseline static analysis for Python

Before opening a pull request, the minimum expected local checks are:

```bash
ruff check src tests
ruff format --check src tests
pytest tests -q
```

## Contribution Guidelines

- Keep changes focused. Avoid mixing refactors, feature work, and unrelated cleanup in one pull request.
- Prefer fixes at the root cause instead of adding behavior-specific patches.
- Preserve the current separation of concerns:
  - `src/core.py` contains business logic and data handling
  - `src/syndi.py` contains the macOS UI layer
  - `src/preferences.py` contains the preferences dialog
- Add or update tests when behavior changes.
- If you introduce a new config key, document it in [README.md](README.md).
- If you change development workflow or contributor expectations, update this file.

## Pull Request Checklist

Use this as a quick pre-PR checklist:

- The change is limited to one clear purpose
- Ruff lint passes
- Ruff format check passes
- Tests pass locally
- README or developer docs are updated if behavior changed
- Release/build impact was considered for packaging-related changes

## Notes for Repository Maintainers

- Public GitHub repositories can use macOS runners and CodeQL without GitHub Actions billing for minutes.
- The release workflow is pinned to `macos-13` for reproducibility.
- The release publishing step runs on Ubuntu because it only uploads the built artifact.
