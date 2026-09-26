#!/usr/bin/env bash
# Regenerate every number reported in the paper from the released raw responses.
# Offline: sends no requests and needs no API key. Python 3.10+, standard library only.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d ../evidence/restored/eval ]; then
  python3 ../evidence/restore_and_verify.py
fi
python3 make_results.py
python3 check_paper.py
