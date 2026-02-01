#!/bin/bash
# Build and run the demo suite inside a Docker container.
# Usage: bash demo/scripts/run_in_docker.sh
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "=== Building Docker image ==="
docker compose -f demo/docker-compose.demo.yml build demo

echo ""
echo "=== Running demo suite in container ==="
docker compose -f demo/docker-compose.demo.yml run --rm demo

echo ""
echo "=== Demo complete ==="
