# Security and privacy

Swing Signal is intended for one user on a trusted laptop. It binds to `127.0.0.1`, checks localhost Host headers and rejects cross-origin JSON mutations. It has no authentication or authorization system for public hosting. Do not expose the service through a public tunnel or bind it to a public interface without designing those controls.

API keys live in the workspace's `connections.json` with `0600` file permissions on macOS/Linux (Windows inherits the workspace folder’s ACLs), or are read from environment overrides. The browser receives configured/not-configured status, not the key. Blank key fields preserve existing keys. Never paste credentials into GitHub issues, chat messages or screenshots.

The SQLite workspace and workspace exports can contain holdings, entry costs, zones and private journal notes. Keep them private. The repository excludes runtime data and includes a staged-content check, but that check is a heuristic and does not replace reviewing what you commit.

Cloud analysis sends public research facts to the selected provider only when requested. It excludes positions and journal text; the provider's retention/data-use terms still apply. Local Ollama is restricted to the loopback endpoint and locally installed models. Provider failures do not trigger another model or paid fallback.

To report a vulnerability, use the repository's **Security → Report a vulnerability** option if available. If private reporting is unavailable, open a minimal issue asking for a private contact without including exploit details, credentials, exports or personal data.
