#!/usr/bin/env bash
# scripts/setup.sh — one-shot dev environment bootstrap
# Usage: bash scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"

echo "==> Creating virtual environment at $VENV"
python -m venv "$VENV"

echo "==> Upgrading pip"
"$VENV/Scripts/pip" install --upgrade pip

echo "==> Installing dependencies (dev)"
"$VENV/Scripts/pip" install -r "$ROOT/requirements-dev.txt"

echo ""
echo "Done!  Activate with:"
echo "  source $VENV/Scripts/activate   (Git Bash / WSL)"
echo "  $VENV\\Scripts\\Activate.ps1      (PowerShell)"
echo ""
echo "Then run:  make help"
