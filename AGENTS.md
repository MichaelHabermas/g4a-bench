# AGENTS.md

## Cursor Cloud specific instructions

### Repository overview

This is **g4a-bench**, a benchmark project for G4A evaluation. As of this writing the repo is an empty scaffold (README + .gitignore only). The `.gitignore` entries suggest a **Python + Node.js** stack is planned.

### Available system tooling

| Tool    | Version (at setup time) |
|---------|------------------------|
| Python  | 3.12                   |
| Node.js | 22.x (via nvm)         |
| pip     | 24.x                   |

### Development notes

- No application code, dependency files, or services exist yet. When code is added, update this file with build/run/test instructions.
- The `.gitignore` covers Python artifacts (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`) and Node.js artifacts (`node_modules/`, `dist/`, `build/`).
- No lint, test, or build commands are configured. Once tooling is added (e.g., `pyproject.toml`, `package.json`), document the commands here.
