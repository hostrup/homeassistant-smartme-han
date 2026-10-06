#!/usr/bin/env bash
set -euo pipefail

echo "=== 1. Pytest ==="
uv run pytest tests/

echo "=== 2. Ruff Lint ==="
uv tool run ruff check custom_components/ tests/

echo "=== 3. Git Status ==="
git status --short

if [ -n "${1:-}" ]; then
  MSG="$1"
  echo "=== 4. Commit & Push ==="
  git add -A
  git commit -m "$MSG

Model: openrouter/deepseek/deepseek-v4.1-flash"
  git push origin main
  echo "=== Udrulning og Push Færdig ==="
fi
