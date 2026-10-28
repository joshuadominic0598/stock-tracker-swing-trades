#!/usr/bin/env python3
"""Apply Ruff formatting and the project's single-blank-line convention."""

import argparse
import io
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def compact_sections(source):
    protected = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING or token.end[0] > token.start[0]:
            protected.update(range(token.start[0], token.end[0] + 1))
    lines = []
    blank = False
    for number, line in enumerate(source.splitlines(keepends=True), 1):
        empty = not line.strip()
        if not empty or not blank or number in protected:
            lines.append(line)
        blank = empty and number not in protected
    return "".join(lines)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = [ROOT / "launch.py"]
    for folder in ("src", "tests", "tools"):
        files.extend(
            path
            for path in (ROOT / folder).rglob("*.py")
            if not {"node_modules", "__pycache__"}.intersection(path.parts)
        )
    changed = []
    for path in sorted(files):
        original = path.read_text(encoding="utf-8")
        formatted = subprocess.run(
            [sys.executable, "-m", "ruff", "format", "--stdin-filename", str(path), "-"],
            input=original,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            check=True,
            cwd=ROOT,
        ).stdout
        formatted = compact_sections(formatted)
        if original != formatted:
            changed.append(str(path.relative_to(ROOT)))
            if not args.check:
                with path.open("w", encoding="utf-8", newline="\n") as output:
                    output.write(formatted)
    if args.check and changed:
        raise SystemExit("Python formatting needed:\n" + "\n".join(changed))
    print(f"Python style {'checked' if args.check else 'formatted'}: {len(files)} files.")

if __name__ == "__main__":
    main()
