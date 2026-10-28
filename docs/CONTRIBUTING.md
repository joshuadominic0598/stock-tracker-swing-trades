# Contributing to Swing Signal

Python serves the API and bundled web interface; SQLite stores the private workspace. Keep responsibilities explicit and use simple functions unless a class has a concrete purpose. Normal app use needs no Node runtime or frontend build.

## Setup

Use Python 3.9+ and Node.js 24+. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
npm --prefix tools/web ci
```

On Windows, replace `.venv/bin/python` with `.venv\Scripts\python`. Installing the package reads its runtime dependencies from `pyproject.toml`, including Windows timezone data. The `dev` extra adds the pinned Python checker. Browser dependencies and their lockfile live together in `tools/web/`.

## Responsibilities and dependency direction

All application paths below are inside `src/swing_signal/`.

| Area             | Responsibility                                                                                                    |
| ---------------- | ----------------------------------------------------------------------------------------------------------------- |
| `analysis/`      | Pure calculations: indicators, zones, retests, flags and candidate ranking. No HTTP, database or AI dependencies. |
| `data/`          | Market feeds, freshness, news/attention and SQLite storage. Uses analysis to build market views.                  |
| `ai/`            | Model catalog, private connection settings, provider transports and evidence-grounded stock analysis.             |
| `workspace.py`   | Validate and save watchlist, zone, position and journal edits; export the workspace.                              |
| `http/routes.py` | Match API paths and delegate to application operations. No SQL or socket handling.                                |
| `http/server.py` | HTTP parsing, loopback/origin checks, response serialization and static assets.                                   |
| `cli.py`         | Startup, port selection, refresh scheduling and browser launch.                                                   |
| `paths.py`       | Locate bundled web assets and the default private workspace.                                                      |
| `web/`           | Browser modules, styles, HTML and unchanged third-party chart assets.                                             |

`launch.py` is a small source-checkout entrypoint. An installed package also exposes `swing-signal` and `python -m swing_signal`. API paths, response fields, cache keys and the existing `data/signaldesk.sqlite3` filename are preserved for compatibility.

Python tests live in `tests/`; offline UI tests and their sample-data generator live in `tools/web/tests/`. The browser suite runs the real source launcher against an isolated workspace.

## Coding style

- Four-space Python indentation, a 100-character target and logically grouped, sorted imports.
- Exactly one blank line between logical sections and functions/methods. Keep blank lines inside multiline strings intact.
- `tools/format_python.py` applies Ruff formatting, then enforces that blank-line convention without changing string values. Use its `--check` mode in CI; standalone `ruff format --check` uses a different top-level spacing convention.
- Comments should explain a non-obvious reason. Avoid decorative separators, obvious narration and large comment blocks. Use descriptive names and small helpers instead.
- Keep routes thin. Validate workspace edits in their application functions and leave protocol concerns in the HTTP handler.
- No speculative interfaces, factories, wrapper classes or inheritance. Catch errors only to provide a useful response or recovery.
- JavaScript uses ES modules, ESLint recommended rules and Prettier. Shared browser/test tooling is configured in `tools/web/`.
- Preserve routes, behavior and financial calculations during cleanup. Declare runtime dependencies in `pyproject.toml`.
- Keep analysis deterministic, dates/units explicit and missing evidence unknown. Provider/model choices must be explicit with no silent fallback.
- Escape user/provider text before inserting HTML. Keep keys on the server and out of URLs, exports, logs and responses. Keep the server bound to loopback.
- Do not reformat vendored third-party assets.

## Verification

```sh
.venv/bin/python -m ruff check .
.venv/bin/python tools/format_python.py --check
.venv/bin/python -m unittest discover -s tests -v
npm --prefix tools/web run check
npm --prefix tools/web exec -- playwright install chromium
npm --prefix tools/web run test:ui
```

Apply safe fixes with `.venv/bin/python -m ruff check . --fix`, `.venv/bin/python tools/format_python.py` and `npm --prefix tools/web run format`. Review the patch and repeat relevant checks.

Browser tests use port 8787 and `--data-dir .tmp/browser-workspace --no-refresh`. Candles are synthetic; external research/model responses are intercepted. User data and paid AI calls are never needed. Set `SIGNALDESK_PYTHON` to another Python executable, or `SIGNALDESK_BROWSER` to an installed Chromium-based browser if necessary. Existing environment variable names remain supported.

Use `SIGNALDESK_SCREENSHOTS=1` with the browser suite to regenerate `docs/images/long-candidates.png`. Inspect the result before committing. Windows can set these variables through `$env:NAME='value'` in PowerShell.

CI repeats Python checks on Linux, macOS and Windows and runs Chromium UI tests. Test coverage does not establish financial performance or complete security.

## Packaging and private data

Build a wheel without copying the workspace:

```sh
.venv/bin/python -m pip wheel --no-deps --wheel-dir .tmp/wheels .
```

The wheel includes Python code, bundled web assets and licenses. From a source checkout, the default workspace remains `data/` beside the launcher. An installed wheel uses `~/.swing-signal/`; `--data-dir` overrides either default. The app creates the directory when first started. Never move an existing user's database or saved keys as part of a refactor.

New workspaces seed the watchlist without holdings. Ignore rules exclude databases, exports, credentials, build artifacts and tool dependencies. Before sharing:

```sh
git add <intended paths>
python3 tools/check_shareable.py
git diff --cached --stat
```

Review the patch too: ignore rules do not protect an already tracked secret. The scanner checks staged content without printing secrets. The empty environment template lives at `docs/examples/.env.example` and is not loaded automatically. Security guidance lives in [SECURITY.md](../.github/SECURITY.md).
