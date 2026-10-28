# Contributing to Swing Signal

Swing Signal is a source-run local app: Python serves the API and static frontend, SQLite stores each user's workspace, and browser modules render the interface. Avoid adding runtime infrastructure when a standard-library implementation is sufficient.

## Setup

Use Python 3.9+ and Node.js 24+. Create a virtual environment and install `requirements-dev.txt`, then run `npm ci`. Windows Python commands use `.venv\Scripts\python` instead of `.venv/bin/python`. The app itself does not need Node, npm or a frontend build.

## Coding conventions

- Python: four spaces, Ruff formatting, 100-character target, sorted imports, no unused names or multiple statements on one line. Settings are in `pyproject.toml`.
- JavaScript: ES modules, ESLint recommended rules, Prettier formatting. Browser globals and test globals are scoped in `eslint.config.js`.
- HTML/CSS/Markdown/JSON/YAML: Prettier. Do not reformat or change vendored third-party files.
- Preserve Python 3.9 compatibility and declare any new runtime dependency explicitly.
- Keep financial rules deterministic and inspectable. Show missing evidence as unknown; never turn missing data into a confident flag.
- Use complete-candle dates, preserve currency/units and avoid forward-looking information in pattern confirmation.
- Provider/model choices must be explicit. No silent retries through a different provider or paid model.
- Escape provider/user text before adding HTML. Keep API keys on the server and out of logs, URLs, exports and responses.
- Keep the server bound to loopback. It has no public-hosting authentication layer.

## Where things live

| Area                                         | Files                                                                |
| -------------------------------------------- | -------------------------------------------------------------------- |
| HTTP routes and startup                      | `server.py`, `launch.py`                                             |
| Workspace storage / private keys             | `app/storage.py`, `app/settings.py`                                  |
| Data fetching, freshness and grouping        | `app/market.py`, `app/config.py`                                     |
| Indicators, flags and setup scores           | `app/indicators.py`, `app/signals.py`                                |
| Automatic zones / support retests            | `app/zones.py`, `app/patterns.py`                                    |
| AI facts, validation and provider transports | `app/intelligence.py`, `app/ai_providers.py`, `app/model_catalog.py` |
| News / discussion / Trends                   | `app/attention.py`                                                   |
| Frontend and charts                          | `web/app.js`, `web/charts.js`, `web/*.css`                           |
| Backend and offline browser tests            | `tests/test_*.py`, `tests/browser/`                                  |

## Checks before submitting

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m unittest discover -s tests -v
npm run check
npx playwright install chromium
npm run test:ui
```

Use `.venv/bin/python -m ruff check . --fix`, `.venv/bin/python -m ruff format .` and `npm run format` to apply formatting and safe fixes. Review the result, then rerun relevant checks.

Browser tests launch an isolated server on port 8787 with `--data-dir .tmp/browser-workspace --no-refresh`. All displayed candles are synthetic; cloud models/research responses are intercepted. User workspace files and paid model calls are never needed. Set `SIGNALDESK_PYTHON` to a different Python executable if required. For an installed Chromium-based browser, `SIGNALDESK_BROWSER` can supply its executable path.

To regenerate the README screenshot from the same illustrative fixture, run browser tests with `SIGNALDESK_SCREENSHOTS=1`. Inspect `docs/images/long-candidates.png` before committing it. Do not publish screenshots of private holdings, keys or notes.

CI repeats lint/format checks, backend tests on multiple Python versions and operating systems, shareability checks, and Chromium UI smoke tests. This is regression coverage, not a claim of complete security or financial correctness.

## Safe sharing

New workspaces seed the curated watchlist but no holdings. Initialization uses insert-if-missing and preserves an existing user's positions and notes. Never copy your `data/` directory into the repository.

Stage intended changes and run:

```sh
python3 scripts/check_shareable.py
git diff --cached --stat
```

Review the staged patch as well. Ignore rules do not untrack an already tracked secret. If a credential was exposed, revoke it with the provider; deleting a file is not credential rotation.

Do not commit `.env`, `connections.json`, SQLite files, workspace exports, local caches, certificates, private keys, virtual environments or `node_modules`. `.env.example` is an empty template and is not loaded automatically.
