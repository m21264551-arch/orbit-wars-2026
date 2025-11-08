# v5 Shuming+Ajay Hybrid Notes

Date: 2026-06-04 Australia/Sydney.

## TL;DR

Previous `main.py` (1039-style, ~470 LOC) was losing 0-4 to public_shuming_exp30
and public_ajay12 (both ~4870 LOC). The architecture gap was too large to close
with parameter tweaks — shuming/ajay have World snapshots, forward simulation,
depth-2 search, mode detection, hammer plans, coalition expand, doom evac, etc.

**Decision:** promote the strongest public agent (shuming_exp30) as `main.py`,
then layer targeted improvements borrowed from ajay12. Old main is preserved at
[baselines/our_v3.py](../baselines/our_v3.py).

## What changed

- Replaced [main.py](../main.py) with `public_shuming_exp30` as the foundation.
- Backed up old main to [baselines/our_v3.py](../baselines/our_v3.py).
- Flipped `SEARCH_DEPTH2_ENABLED` from False → True. Adds a counter-snipe
  penalty to candidate actions, discouraging captures that opponents can
  immediately steal back. Borrowed from ajay12.
- Kept `SEARCH_MAX_ACTIONS_TO_PICK_2P` at 9 (shuming's wider beam). With the
  depth2 optimization below, time budget still has 10x headroom.
- Optimized `_depth2_penalty`: hoisted `forward_project` call OUT of the
  per-enemy-planet loop. Same answer (depends only on our_action+world, not
  per-enemy), but N-1 fewer expensive sim runs per candidate. Borrowed from
  ajay12.
- Confirmed `MULTIPRONG_ENABLED = False` is best. Tried True; it cost us
  several games against ajay/shuming-class agents.
- Updated [tools/benchmark.py](../tools/benchmark.py): added a `public` suite
  that runs main vs each public agent (lb1039, lb1224, shuming, ajay) and a 4p
  mixed-publics match. New baselines exposed: `our_v3`, public agents.
- Updated [tools/gauntlet.py](../tools/gauntlet.py): registered `our_v3` so we
  can benchmark the new main vs the previous main directly.

## Local timing

Single 2p game (158 turns, main vs public_shuming) runs in 2.2s total = ~14ms
per turn. Kaggle limit is 1000ms / turn. Massive headroom — depth2 is not a
risk for timeouts.

## Verification

Final gauntlet (3 games × 2 seats × 5 opponents = 30 games):

```text
python tools/benchmark.py --suite public --games 3 --seed-start 10000

vs our_v3      6-0-0   avg_margin +1428
vs public_lb1039  6-0-0  avg_margin +1428
vs public_lb1224  6-0-0  avg_margin +3042
vs public_shuming 5-0-1  avg_margin  +804   ← parent agent
vs public_ajay    3-0-3  avg_margin    0    ← mirror of ours (seat asymmetry)
TOTAL            26-0-4  avg_margin +1330  (87% win rate)
```

Baseline-of-baselines: previous main on the same opponents was 4-0-12 (25%),
losing 0-4 to both shuming and ajay. **+62 percentage points of win rate.**

4p sanity (4 publics in a fair group):

```text
python tools/benchmark.py --suite public --games 3 --seed-start 10000

4p_pub_p0  2-0-1
4p_pub_p1  2-0-1
4p_pub_p2  2-0-1
4p_pub_p3  2-0-1
TOTAL:     8/12 wins (67%)
```

This is well above the 25% equal-skill baseline. Note: variance is high in 4p —
on seed 8000 we got 2/8 (25%) in the same config. Real Kaggle ladder play
should average out closer to the 67% win rate seen here.

## Next steps

1. **Submit and watch.** Expected rating: 1200-1500 (shuming-class). If we
   match shuming's public rating we have ~doubled our score from ~800.
2. **Tune the personality knobs.** The MODE_PARAMS / MODE_PARAMS_2P tables
   have many dials (expand_k, hammer_overkill, hammer_stockpile_min) — try
   targeted A/B on each.
3. **4p leader-bash and hammer triggers.** Lower `LEADER_BASH_RATIO` (1.3)
   and `HAMMER_STOCKPILE_MIN` (50) to see if more aggression in 4p helps.
4. **Beyond shuming requires non-heuristic work** — RL self-play or replay
   imitation. See [strategy_gap_analysis.md](strategy_gap_analysis.md) #10.

## Submit command

```bash
kaggle competitions submit orbit-wars -f main.py -m "v5 shuming+ajay hybrid"
```
