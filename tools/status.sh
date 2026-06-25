#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

kaggle competitions submissions -c orbit-wars

if [[ $# -gt 0 ]]; then
  echo
  kaggle competitions episodes "$1"
fi
