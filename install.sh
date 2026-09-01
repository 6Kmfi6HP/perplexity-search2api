#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================================"
echo "  Perplexity Search2API & Agent Skills Installer"
echo "========================================================"

# 1. Install CLI
if command -v uv >/dev/null 2>&1; then
    echo ">> Installing pplx CLI via uv tool..."
    uv tool install --force --editable .
elif command -v pip >/dev/null 2>&1; then
    echo ">> Installing pplx CLI via pip..."
    pip install -e .
else
    echo "ERROR: Neither uv nor pip found. Please install Python 3.10+ and uv." >&2
    exit 1
fi

# Ensure ~/.local/bin is in PATH for current shell
export PATH="$HOME/.local/bin:$PATH"

# 2. Verify pplx CLI
if command -v pplx >/dev/null 2>&1; then
    echo ">> pplx CLI installed successfully at: $(which pplx)"
else
    echo "WARNING: pplx installed in ~/.local/bin. Ensure ~/.local/bin is in your PATH."
fi

# 3. Link skills for local agent discovery (Claude Code & Codex)
AGENTS_SKILLS_DIR="$HOME/.agents/skills"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills"

mkdir -p "$AGENTS_SKILLS_DIR"
mkdir -p "$CLAUDE_SKILLS_DIR"

echo ">> Linking skill into ~/.agents/skills/pplx..."
rm -rf "$AGENTS_SKILLS_DIR/pplx"
ln -s "$SCRIPT_DIR/skills/pplx" "$AGENTS_SKILLS_DIR/pplx"

echo ">> Linking skill into ~/.claude/skills/pplx..."
rm -rf "$CLAUDE_SKILLS_DIR/pplx"
ln -s "$SCRIPT_DIR/skills/pplx" "$CLAUDE_SKILLS_DIR/pplx"

echo "========================================================"
echo "  Installation Complete!"
echo "  Try running: pplx info"
echo "========================================================"
