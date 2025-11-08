#!/usr/bin/env bash
# A/B harness for Producer-style planner vs frozen v6.1 baseline.
# Usage:
#   tools/ab_v61.sh <seed>          # 4P 5-group gauntlet at <seed>, 80 games each side
#   tools/ab_v61.sh <seed> instr    # same, with V64_INSTRUMENT=1 on the candidate
#
# Writes:
#   notes/val_producer_4p_<seed>.csv     # candidate (V65_PRODUCER_4P=1)
#   notes/val_v61_4p_<seed>.csv          # frozen baseline (env-var-proof)
#   notes/v64_producer_4p_<seed>.jsonl   # candidate activation data (if instr)
#
# The frozen baseline lives at baselines/main_v61_baseline.py with 44 env reads
# inlined. It's immune to V64_/V65_/etc env vars — so a stray export in the
# candidate run won't contaminate the baseline.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SEED="${1:?usage: tools/ab_v61.sh <seed> [instr]}"
INSTR="${2:-}"

CANDIDATE_OUT="notes/val_producer_4p_${SEED}.csv"
BASELINE_OUT="notes/val_v61_4p_${SEED}.csv"
INSTR_OUT="notes/v64_producer_4p_${SEED}.jsonl"

GAMES=4
GROUPS=5

CANDIDATE_ENV="V65_PRODUCER_4P=1"
if [ "$INSTR" = "instr" ]; then
  rm -f "$INSTR_OUT"
  CANDIDATE_ENV="V65_PRODUCER_4P=1 V64_INSTRUMENT=1 V64_INSTR_FILE=$INSTR_OUT"
fi

echo "=== A/B at seed $SEED (${GAMES} games × ${GROUPS} groups × 4 seats = $((GAMES*GROUPS*4)) games per side) ==="
echo "Candidate:  subject=main env=$CANDIDATE_ENV"
echo "Baseline:   subject=main_v61_baseline (frozen)"
echo ""

echo "--- candidate ---"
eval "$CANDIDATE_ENV python tools/gauntlet.py --subject main --suites 4p \
  --games $GAMES --max-4p-groups $GROUPS --seed-start $SEED \
  --output $CANDIDATE_OUT" 2>&1 | tail -3

echo ""
echo "--- baseline ---"
python tools/gauntlet.py --subject main_v61_baseline --suites 4p \
  --games $GAMES --max-4p-groups $GROUPS --seed-start "$SEED" \
  --output "$BASELINE_OUT" 2>&1 | tail -3

echo ""
echo "=== SUMMARY ==="
python3 - <<EOF
import csv
def agg(p):
    rows = [r for r in csv.DictReader(open(p)) if not r['suite'].startswith('#')]
    w = sum(int(r['wins']) for r in rows)
    l = sum(int(r['losses']) for r in rows)
    g = sum(int(r['games']) for r in rows)
    m = sum(float(r['avg_margin'])*int(r['games']) for r in rows)/g if g else 0
    return w, l, g, m

wc, lc, gc, mc = agg("$CANDIDATE_OUT")
wb, lb, gb, mb = agg("$BASELINE_OUT")
print(f"candidate (Producer): {wc}/{gc} wins, margin {mc:+.1f}")
print(f"baseline  (v6.1)    : {wb}/{gb} wins, margin {mb:+.1f}")
print(f"Δ                    : {wc-wb:+d} wins, {mc-mb:+.1f} margin")
print()
print("Per-group:")
def per_group(p):
    rows = [r for r in csv.DictReader(open(p)) if not r['suite'].startswith('#')]
    by = {}
    for r in rows:
        g = r['opponents']
        by.setdefault(g, [0,0])
        by[g][0] += int(r['wins'])
        by[g][1] += int(r['games'])
    return by
gc_ = per_group("$CANDIDATE_OUT")
gb_ = per_group("$BASELINE_OUT")
for g in gc_:
    wc_, tc_ = gc_[g]
    wb_, tb_ = gb_.get(g, (0,0))
    print(f"  {g}: cand={wc_}/{tc_}  base={wb_}/{tb_}  Δ={wc_-wb_:+d}")
EOF
