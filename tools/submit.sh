#!/usr/bin/env bash
set -euo pipefail

MESSAGE="${1:-heuristic expansion defender}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"
python tools/benchmark.py --games 10
kaggle competitions submit orbit-wars -f main.py -m "$MESSAGE"
kaggle competitions submissions orbit-wars
