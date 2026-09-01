# Contributing to Perplexity Search2API

Thank you for your interest in contributing to **Perplexity Search2API**! We welcome bug reports, feature requests, documentation improvements, and pull requests.

---

## 🛠️ Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/6Kmfi6HP/perplexity-search2api.git
   cd perplexity-search2api
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies in editable mode:**
   ```bash
   pip install -e ".[dev]"
   # or with uv:
   uv pip install -e ".[dev]"
   ```

4. **Run tests:**
   ```bash
   pytest
   ```

---

## 📋 Git Commit Guidelines

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` A new feature
- `fix:` A bug fix
- `docs:` Documentation only changes
- `style:` Changes that do not affect the meaning of the code (formatting, missing semicolons, etc.)
- `refactor:` A code change that neither fixes a bug nor adds a feature
- `perf:` A code change that improves performance
- `test:` Adding missing tests or correcting existing tests
- `chore:` Changes to the build process or auxiliary tools and libraries

**Example:**
```bash
git commit -m "feat(auth): support PERPLEXITY_SESSION_TOKEN environment variable fallback"
```

---

## 🔒 Security & Privacy Notice

- **NEVER commit sensitive session credentials** (`.perplexity_session.json`, cookies, auth tokens, personal API keys).
- Verify that `.gitignore` is intact before staging files (`git status`).
- If you notice accidental leakage in your branch or PR, rewrite your git history before opening or updating a PR.

---

## 🧪 Testing Guidelines

- Write tests for new features and bug fixes under the `tests/` directory.
- Ensure all tests pass prior to submitting a pull request:
  ```bash
  pytest -v
  ```

---

## 🚀 Pull Request Process

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. Make sure your code adheres to project standards and formatting.
3. Add tests to cover your changes.
4. Ensure all tests pass.
5. Push to your fork and submit a Pull Request describing your changes, motivation, and test coverage.
