#!/bin/sh
# Thin shim → install.py (stdlib Python 3, no pip install needed).
DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }
exec python3 "$DIR/install.py" "$@"
