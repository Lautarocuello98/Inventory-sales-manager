#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q
ruff check .

if command -v rg >/dev/null 2>&1; then
  mapfile -t py_files < <(rg --files src -g "*.py")
else
  mapfile -t py_files < <(find src -type f -name "*.py")
fi

python -m py_compile "${py_files[@]}"

echo "Release checks passed"
