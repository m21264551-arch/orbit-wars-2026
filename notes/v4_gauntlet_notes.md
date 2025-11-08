# v4 Gauntlet Notes

Date: 2026-06-03 Australia/Sydney.

## What changed

- Extracted public-kernel agents into runnable baselines with `tools/extract_public_agents.py`.
- Added `tools/gauntlet.py` for 2p/4p seat-rotated local tournaments against public and custom pools.
- Built an experimental timeline/hammer agent at `baselines/v4_timeline_hammer.py`.
- Restored `main.py` to the stable 1039-style foundation after the experimental path underperformed.

## Verification

Stable `main.py`:

```text
python tools/benchmark.py --suite quick --games 5 --seed-start 400

2p_starter_p0: 5-0, avg_margin 16302.2
2p_starter_p1: 5-0, avg_margin 16336.8
4p_mixed_p0: 5-0, avg_margin 24234.2
```

Experimental `baselines/v4_timeline_hammer.py`:

- Added arrival-ledger/timeline projection, richer scoring, and hammer attack scaffolding.
- Failed the direct 1039 gate in 2p, so it is kept as an experiment rather than promoted to `main.py`.

## 2026-06-03 Ratchet Pass

Promoted to `main.py`:

- Fixed source locking after reinforcement: `used_planets` now compares planet IDs consistently instead of mixing source IDs and planet-array indices. This keeps a planet that already launched a defensive reinforcement from being reused offensively when IDs diverge from array positions.

Tested but not promoted:

- Phase-aware low neutral score floor: improved some margins, but lost too many binary 2p outcomes.
- 4p leader-pressure multiplier: same win count as stable on the fair 4p slice, with worse margin.
- Dynamic comet-sweep relaxation: helped one 2p slice, then hard-failed a broader 2p slice.

Final promoted checks:

```text
python -m py_compile main.py tools/*.py baselines/*.py
python tools/benchmark.py --suite quick --games 5 --seed-start 900

2p_starter_p0: 5-0, avg_margin 17980.2
2p_starter_p1: 5-0, avg_margin 17980.2
4p_mixed_p0: 5-0, avg_margin 17204.6

python tools/gauntlet.py --subject main --opponents public_lb1039 --suites 2p --games 3 --seed-start 201

aggregate: 0 wins, 6 ties, 0 losses, avg_margin 0.0
```

## 2026-06-03 Big Patch Attempt

Promoted state:

- `main.py` remains on the stable 1039-style foundation plus the source-lock bugfix. This is still the current safe submission baseline.

Tested but not promoted:

- All-board enemy-fleet defense collision: intended to avoid reserving ships for fleets that hit another planet first. Rejected after a 4p gate went 0-8 against the public mix.
- Source-radius intercept aiming: used the existing `source_radius` parameter in `solve_intercept`. Rejected after losing the 2p gate against `public_lb1039`.
- Late multi-source hammer: combined several sources against high-production enemy planets when no single source could capture. Rejected after a 2p gate went 1 win, 2 ties, 5 losses.

Final safe checks after rollbacks:

```text
python -m py_compile main.py tools/*.py baselines/*.py
python tools/benchmark.py --suite quick --games 5 --seed-start 1300

2p_starter_p0: 5-0, avg_margin 10507.4
2p_starter_p1: 5-0, avg_margin 10507.4
4p_mixed_p0: 5-0, avg_margin 12182.6

python tools/gauntlet.py --subject main --opponents public_lb1039 --suites 2p --games 3 --seed-start 301

aggregate: 0 wins, 6 ties, 0 losses, avg_margin 0.0
```

## Next useful gauntlet commands

```bash
python tools/extract_public_agents.py
python tools/gauntlet.py --subject main --opponents public --suites 2p --games 3 --seed-start 100
python tools/gauntlet.py --subject main --opponents public --suites 4p --games 2 --seed-start 200 --max-4p-groups 3
python tools/gauntlet.py --subject main --opponents all --suites 2p,4p --games 5 --seed-start 100 --output notes/gauntlet_latest.csv
```
