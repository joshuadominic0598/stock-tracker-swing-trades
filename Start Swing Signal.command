#!/bin/zsh
cd "${0:A:h}"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.9 or later is required. Install Python from https://www.python.org/downloads/macos/"
  read "?Press Return to close."
  exit 1
fi
python3 launch.py
