#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q
ruff check .
python -m py_compile $(rg --files src | tr '\n' ' ')

echo "Release checks passed"