#!/usr/bin/env bash
set -euo pipefail

# Helper wrapper to invoke pplx CLI reliably across environments
if command -v pplx >/dev/null 2>&1; then
    exec pplx "$@"
elif [ -f "$HOME/.local/bin/pplx" ]; then
    exec "$HOME/.local/bin/pplx" "$@"
elif command -v uv >/dev/null 2>&1; then
    exec uv --directory "$(dirname "$0")/../../.." run pplx "$@"
else
    echo "ERROR: pplx CLI command not found in PATH or ~/.local/bin" >&2
    echo "Run ./install.sh to install the package." >&2
    exit 1
fi
