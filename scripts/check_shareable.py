#!/usr/bin/env python3
"""Reject private workspace files and likely credentials in the Git index."""

import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(rb"gsk_[A-Za-z0-9_-]{30,}"),
    re.compile(rb"AIza[A-Za-z0-9_-]{30,}"),
    re.compile(rb"sk-(?:proj-)?[A-Za-z0-9_-]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
)


def main():
    raw = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=ROOT)
    files = [name.decode() for name in raw.split(b"\0") if name]
    if not files:
        raise SystemExit("No staged/tracked files to check. Stage the intended source first.")
    secrets = []
    try:
        config = json.loads((ROOT / "data/connections.json").read_text())
        secrets = [str(v).encode() for k, v in config.items() if k.endswith("_api_key") and v]
    except (OSError, ValueError, AttributeError):
        pass
    secrets.extend(
        os.environ[name].encode()
        for name in ("GEMINI_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY")
        if os.environ.get(name)
    )
    findings = []
    for name in files:
        path = Path(name)
        private = (
            (
                name.startswith(
                    (
                        "data/",
                        "exports/",
                        "backups/",
                        ".venv/",
                        "node_modules/",
                        ".tmp/",
                        "docs/previews/",
                    )
                )
                and name != "data/.gitkeep"
            )
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.suffix in (".sqlite", ".sqlite3", ".db", ".pem", ".key")
            or path.name.endswith(("-wal", "-shm"))
        )
        if private:
            findings.append(name + ": private/runtime file")
            continue
        content = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
        if any(pattern.search(content) for pattern in PATTERNS) or any(
            secret in content for secret in secrets
        ):
            findings.append(name + ": possible credential (value withheld)")
    if findings:
        raise SystemExit("Shareability check failed:\n" + "\n".join(findings))
    print(f"Shareability check passed: {len(files)} files; no private state or known credentials.")


if __name__ == "__main__":
    main()
