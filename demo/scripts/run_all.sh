#!/bin/bash
# Run the full demo test suite locally.
# Usage: bash demo/scripts/run_all.sh
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "=== ricet Demo Suite ==="
echo ""

# Run existing unit tests first
echo "--- Step 1: Unit tests ---"
python -m pytest tests/ -q --tb=line
echo ""

# Run demo phases sequentially
echo "--- Step 2: Demo phases ---"
python -m pytest demo/ -v --tb=short -x
echo ""

echo "=== All demo phases passed ==="
