# Contributing to AMR Sentinel

Thank you for your interest in contributing. This document describes how to file issues, propose changes, and submit pull requests.

## Code of conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you agree to uphold it. Please report unacceptable behavior to the maintainers at the address listed in [`SECURITY.md`](SECURITY.md).

## Getting help

- **Questions about usage**: open a [GitHub Discussion](../../discussions) (preferred) or a question-type issue.
- **Suspected bugs**: open an [issue](../../issues/new/choose) using the bug report template.
- **Feature ideas**: open an [issue](../../issues/new/choose) using the feature request template, or start a Discussion first if the scope is large.
- **Security vulnerabilities**: do not open a public issue. Follow the process in [`SECURITY.md`](SECURITY.md).

## Development environment

### Prerequisites

- Python 3.12 or later
- Node.js 20 or later (for the frontend)
- Java 21 or later (for the gateway)
- Docker Desktop with Docker Compose v2
- Approximately 8 GB of free RAM for the full local stack

### Initial setup

```bash
# Clone your fork and add the upstream remote
git clone https://github.com/<your-handle>/amr-sentinel.git
cd amr-sentinel
git remote add upstream https://github.com/Tej-Katika/amr-sentinel.git

# Copy environment defaults
cp .env.example .env

# Bring up the local stack
docker compose up -d

# Install Python dev dependencies
pip install -r requirements-dev.txt

# Run the smoke test to confirm the stack is working
python scripts/smoke_test.py
```

The `Makefile` wraps common operations. Run `make help` for the full list.

## Branching and pull requests

1. **Create a feature branch from `main`**. Use a descriptive name such as `fix/breakpoint-classifier-edge-case` or `feat/glass-export-quality-checks`.
2. **Keep pull requests focused**. One logical change per PR. Large refactors should be broken into smaller, reviewable steps.
3. **Write a descriptive PR title and body** explaining the motivation, the change, and any testing performed. The PR template will prompt you.
4. **Link related issues** in the PR body using `Closes #123` or `Refs #123`.
5. **All checks must pass** before review: tests, linters, formatters, type checks.
6. **Address review feedback** by pushing new commits to the branch (do not force-push during review unless asked).

## Coding standards

### Python

- **Formatter**: [`ruff format`](https://docs.astral.sh/ruff/formatter/) (configured in `pyproject.toml` when present, otherwise defaults).
- **Linter**: [`ruff check`](https://docs.astral.sh/ruff/linter/).
- **Type hints**: required on all new public functions and class methods. Use `from __future__ import annotations` where helpful.
- **Docstrings**: Google style for modules, classes, and public functions.
- **Tests**: every new module needs at least one unit test. Aim for behavior coverage, not line coverage.

### TypeScript / Frontend

- **Formatter**: Prettier defaults.
- **Linter**: ESLint with the project configuration.
- **Components**: functional components with hooks. Avoid class components.
- **State**: prefer local state and React Query for server state. Justify any global state addition in the PR.

### Java / Gateway

- **Style**: Google Java Style.
- **Tests**: JUnit 5. Integration tests use Testcontainers.

### Commit messages

- Imperative mood: "Add classifier for OXA-48 family" not "Added classifier".
- First line under 72 characters.
- Body paragraphs wrapped at 72 characters explaining *why*, not *what*.
- Reference related issues at the end: `Refs #123` or `Closes #123`.

## Testing

```bash
pytest                          # all tests
pytest -m "not slow"            # fast tests only (skip algorithm-heavy tests)
pytest services/intelligence    # one service
pytest -k breakpoint            # tests matching a keyword
```

Before opening a PR, please ensure:

- [ ] `pytest` passes
- [ ] `ruff check .` passes
- [ ] `ruff format --check .` passes
- [ ] Any new functionality has tests
- [ ] Any new behavior is documented in the relevant README or docstring

## Documentation

- User-facing changes require a corresponding update to `README.md` or `docs/`.
- Architectural changes require an update to `docs/ARCHITECTURE.md`.
- New environment variables must be added to `.env.example` with a comment explaining their purpose.

## Data handling

This project processes healthcare-adjacent data. Contributors must:

- **Never commit real patient data**, including test fixtures derived from real data.
- **Never commit credentials** or API keys, even in tests. Use `.env` (which is gitignored) and the patterns shown in `.env.example`.
- **Treat any data from controlled-access registries (such as Vivli, GLASS country data) as out of scope** for this repository. AMR Sentinel is the platform; analysis on specific datasets belongs in separate repositories that depend on this one.

## Releases

Releases are tagged from `main` using semantic versioning (`MAJOR.MINOR.PATCH`). Pre-1.0 versions may make breaking changes between minor versions; the release notes will call these out.

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
