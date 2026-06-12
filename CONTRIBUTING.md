# Contributing to Developer Core

Thanks for your interest. This guide gets you set up and submitting your first PR.

---

## Getting Started

1. **Fork** the repo and clone your fork
2. Set up your local environment — follow the [Quickstart in README.md](README.md#quickstart)
3. Create a branch: `feat/<short-description>` or `fix/<short-description>`
4. Make your changes
5. Run the tests (see below)
6. Open a pull request against `master`

---

## Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feat/<description>` | `feat/add-coding-round-timer` |
| Bug fix | `fix/<description>` | `fix/celery-worker-crash-on-restart` |
| Docs | `docs/<description>` | `docs/update-ngrok-setup-guide` |
| Chore | `chore/<description>` | `chore/upgrade-fastapi-version` |

---

## Running Tests

```bash
# Backend tests
cd backend
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements-ci.txt
pytest tests/ -v --ignore=tests/integration --ignore=tests/test_db_connections.py

# Frontend type check
cd frontend
npm run type-check
```

---

## Code Style

- **Backend:** Follow the layering in [ARCHITECTURE.md](ARCHITECTURE.md) — route → service → repository. No business logic in route handlers.
- **Frontend:** One component per file. No business logic in components — extract to hooks.
- **Naming:** See Section 4.3 of [ARCHITECTURE.md](ARCHITECTURE.md).

---

## Commit Messages

Imperative, present tense. Describe what the commit does, not what you did.

```
# Good
feat: add resume tailoring for Greenhouse ATS
fix: prevent celery worker crash on Redis reconnect

# Not good
Added resume tailoring
fixed a bug
```

---

## Pull Request Process

1. Keep PRs focused — one feature or fix per PR
2. Fill in the PR template fully
3. Link the issue your PR resolves (`Closes #123`)
4. All tests must pass
5. A maintainer will review within 48 hours

---

## Good First Issues

New to the codebase? Issues labelled [`good first issue`](https://github.com/Statosco/developer-core/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) are scoped to be achievable without deep knowledge of the full system.

---

## Code of Conduct

Be respectful. Critique code, not people. That's it.
