# Producer-style Planner — scope & A/B contract

Date: 2026-06-05. Operating brief: [leaderboard_maximizer_prompt.md](leaderboard_maximizer_prompt.md).

## Goal

Beat the frozen `v6.1` baseline on **every** held-out 4P validation range
([baselines/main_v61_baseline.py](../baselines/main_v61_baseline.py),
44 env reads inlined to defaults so the baseline can't drift). Goal is
**not** parity within noise — we want a measurable, distributed win
across seed ranges, against the full opponent pool, with no
catastrophic single-cell regression.

## Why a planner, not a constant tweak

The data is decisive. Top 4P winners launch ~1007 ships by turn 75; we
launch 256. They run 6.45 active fleets at turn 75; we run 2.50. That's
a 3–4× throughput gap. No threshold tweak inside a maturely-tuned
heuristic closes a 3–4× gap — every single-toggle since v6.1
(v6.2, depth-2 4P, cheap-pickup 4P, V64 brain-lead) has bottomed at the
±2 / 80-game noise floor. See [v6_param_tuning_notes.md](v6_param_tuning_notes.md)
for the full ablation graveyard.

## What "Producer-style" means here

Reference: `slawekbiel/the-producer-agent` public notebook. The
distinguishing behaviors vs our current expand chain are:

1. **Target-first iteration.** For each candidate target, score it by
   present value, then find the best source — don't go source-first
   (which is greedy from the wrong end and under-uses idle backline
   planets).
2. **Many waves per turn.** 6+ launches in midgame, not 1–4. Active
   fleets at turn 75 is the gap to close.
3. **Multi-source synchronized arrival** (later phase). A single source
   sending 30 ships is dead. Two sources sending 25 each arriving on the
   same turn capture a 50-garrison enemy.
4. **Regroup pass.** Ships not committed to expand/defense push toward
   the pressure frontier rather than sitting on backline planets.

## What the existing `handle_four_p_compound_pressure` already does

It's an attempt at #1+#2 but failed: 0-8 on seed 610000, gated off
since v6.2. The diagnosis from the notes: "overcommit … needs timeline
defense/arrival safety, not just production-weighted greed." Reading
the code at [main.py:3507](../main.py:3507), it iterates source-first
(not target-first), uses an ad-hoc additive score (not present value),
and caps at 4 waves/turn. The Producer replaces this pass rather than
running alongside it.

## Phase plan

Each phase is gated by `V65_PRODUCER_4P` env var, default `"0"` (off).
Each phase A/Bs against `main_v61_baseline`. We promote a phase by
flipping the default to `"1"` only if it clears the gates below.

### Phase A — target-first ROI greedy (single-source)

For each potential target (enemy or neutral with prod ≥ 2 in 4P),
compute a present-value score:

```
score = sum(production * decay^t for t in horizon) - cost(ships) - risk
```

where `horizon` is the projected hold duration (200 turns or until end
of game), `decay` is `0.97`, `cost(ships)` is the ships needed plus an
overkill margin, and `risk` is a danger weight from nearby enemy ships.

Sort targets descending by score. Pick the top K (K=6 in midgame, 8 in
endgame). For each picked target, find the single best source that can
arrive within `producer_max_travel`, has surplus after defense reserve,
and passes existing safety checks (anti-snipe, endgame ROI, neutral
tempo). Commit the wave.

Reuse: `aim_at_target`, `compute_planet_reserve`, `plan_solo_capture`,
`_capture_holds_against_snipe`, `_endgame_roi_ok`,
`_neutral_tempo_ok`, `forward_project`. The Producer should be
parasitic on existing safety infrastructure, not invent its own.

### Phase B — multi-source synchronized waves

For high-value targets where no single source can win solo, find a
set of sources whose combined arrivals can capture, with arrival times
clustered ≤ 2 turns apart (so a defender can't reinforce between
waves). Use the existing `_try_coalition_expand` or build a similar
synchronized launcher.

### Phase C — regroup pass

After Phase A+B + accumulator + mega-hammer + hammer, any planet whose
`available[p.id] - spent[p.id]` exceeds a reserve floor and is not
mode-log-tagged sends surplus toward the closest contested or frontier
planet.

## A/B harness

Standard runs (all 4P, 5-group spread, 80 games each):

```bash
# Candidate
V65_PRODUCER_4P=1 python tools/gauntlet.py --subject main --suites 4p \
  --games 4 --max-4p-groups 5 --seed-start 700000 \
  --output notes/val_producer_4p_700k.csv

# Baseline (frozen v6.1, env-var-proof)
python tools/gauntlet.py --subject main_v61_baseline --suites 4p \
  --games 4 --max-4p-groups 5 --seed-start 700000 \
  --output notes/val_v61_4p_700k.csv
```

The frozen baseline is the same file regardless of env vars, so the
A/B is clean even if we accidentally export `V65_PRODUCER_4P=1` to the
baseline run.

## Acceptance gates (per phase promotion)

A phase moves from `default off` to `default on` only if **all** hold:

1. **Compile + smoke** — `python -m py_compile main.py` and a 1-game
   public benchmark show no runtime errors and no act timeouts.
2. **No 2P regression** — Phase A/B/C are gated by `world.is_2p == False`.
   2P should be byte-identical to baseline by construction. Spot-check
   one 2P benchmark to confirm.
3. **Held-out 4P** — ≥ baseline wins on seeds 700000, 800000, **and**
   900000 (5-group spread, 80 games each). Total Δ ≥ +6 wins across
   240 games. A single range with Δ < 0 wins is acceptable only if the
   other two are Δ ≥ +4.
4. **No matchup collapse** — no single (group, seat) cell loses
   ≥ 4 / 4 games where baseline won ≥ 2 / 4.
5. **Activation evidence** — with `V64_INSTRUMENT=1`, the Producer
   tag (`producer-launch`) should fire in ≥ 50 % of 4P games and the
   per-game launch volume by turn 75 should be ≥ +30 % vs baseline.
   This is a sanity check that the planner is actually doing something,
   not that it's just lucky.

If a phase fails any gate, env var stays `"0"` and we iterate. We do
not stack phases — each one must clear independently against the
frozen v6.1.

## Anti-patterns from prior failures (do not repeat)

- **Single good seed proves nothing.** v6.2 payload-pressure was +121
  margin on seed 600000 and 0-8 on seed 610000.
- **Two ranges is not enough.** v6.2 (+2 / 700k) and depth-2 4P
  (+3 / 700k, +2 / 800k) both passed two-range checks and reversed on
  range three.
- **Concentrated signal is suspicious.** v6.2's +2 was entirely on
  group E. Distributed Δ across groups is more believable.
- **Don't trust frozen-self baselines for promotion.** They're useful
  for fast iteration but not a sufficient acceptance gate. The frozen
  v6.1 baseline here IS our real opponent — same agent — so the test is
  "does the Producer beat the version of itself it was branched from".
- **Don't ship without `V64_INSTRUMENT` evidence.** If the Producer
  doesn't measurably change launch volume, any win count delta is luck.

## Open questions to resolve during Phase A

1. **What is "horizon"?** Game ends at turn 500. Discount factor 0.97
   over 200 turns weights present production at ~6.6× endgame
   production. Plausible. Need to verify the formula matches the
   replay-derived value gradient.
2. **Should the Producer respect `mode_log` from prior subsystems?**
   Yes — it runs AFTER expand/cheap-pickup/accumulator. A source
   already used by another subsystem this turn is unavailable.
3. **K = 6 in midgame: where does the budget come from?** Sources
   currently idle after expand. Need to verify there are 6 idle sources
   on average per turn — instrumentation already captures
   `actions` per checkpoint; can derive idle-source count from
   `my_planets - actions` (rough).

## Status

- Frozen baseline: [baselines/main_v61_baseline.py](../baselines/main_v61_baseline.py) ✅
- Registered in gauntlet: `main_v61_baseline` ✅
- Instrumentation: `V64_INSTRUMENT=1` ✅
- A/B harness: [tools/ab_v61.sh](../tools/ab_v61.sh) ✅
- Phase A: ❌ **all three iterations bottom out at noise floor.** Not promotable.
- Phase B: planned, see "Phase B design" below.

### Phase A iteration log (all 320 games, seed 700k, full 20-group spread)

| Variant | Wins Δ | Margin Δ |
|---|---:|---:|
| v1 (Producer before stockpile chain) | +1 / 320 | +16.6 |
| v2 (Producer moved to after `handle_hammer`) | +3 / 320 | +209.6 |
| v3 (v2 + lead-only gate, `my_prod_share >= 0.25`) | +0 / 320 | +155.0 |
| v2 on seed 800k (cross-validation) | **−4 / 320** | +46.8 |

Distributed per-group pattern was consistent across iterations: **+1
to +4 wins vs weak-opponent groups (rahul-heavy), −1 to −3 wins vs
strong-opponent groups (shuming+ajay)**. Net depends on group mix. v3
killed the in-tight-game Producer activity but also killed the in-easy-
game gains. Net = noise floor.

### Phase A activation profile (V65=1, smoke 12 games seed 700k group E)

| Tag | v1 | v2 | v3 |
|---|---:|---:|---:|
| producer-launch | 12/12 | 12/12 | 11/12 |
| brain-reserved-lead | 0/12 | 1/12 | 1/12 |
| accumulator-feeder | 2/12 | 3/12 | 2/12 |
| mega-hammer-launched | 0/12 | 0/12 | 1/12 |
| hammer | 10/12 | 11/12 | 11/12 |

The chain partially recovers when Producer runs after `handle_hammer`,
but mega-hammer's own 200-ship floor (not chain contention) is the
bottleneck on its activation.

### Why Phase A failed

The hypothesis was: target-first ROI iteration with PV scoring would
unlock launches the source-first expand/compound-pressure chain misses.
The data refutes this:

1. The existing `_handle_search_expand_4p` + `handle_expand` chain is
   already roughly target-quality-aware and picks the same source-target
   pairs Phase A would pick — Phase A mostly just reshuffles the
   ordering.
2. Adding a separate pass doesn't add *new* (src, tgt) pairs; it just
   spends the same residual surplus differently. Net effect = noise.
3. The activation-tag instrumentation shows producer-launch fires
   12/12 games, but turn-75 launch volume only moves from ~25 actions to
   ~28 actions per game. ~3 extra waves per game is not 3× throughput.
4. The Producer-style insight from top replays is **multi-source
   synchronized waves**, not target-first ordering. Phase A doesn't
   implement that.

### What the data still says we need

Top 4P winners (TonyK, Jake Will, 213tubo per
[v6_param_tuning_notes.md](v6_param_tuning_notes.md)):

- turns 51-75 ships launched: ~1007 vs our 256 (~4× gap)
- turns 51-75 average wave size: 45-49 ships vs our 28
- turns 51-75 max wave size: 121-130 ships vs our 56
- active fleets at turn 75: 6.45 vs our 2.50

Note especially the *max* wave size — top bots regularly fire 100+ ship
waves. We rarely do. That's a single planet with 100+ ships, OR a
coordinated multi-source wave summing to 100+ ships. Both are missing
from our current behavior.

### Phase B design — multi-source synchronized waves

For each high-value target whose required force exceeds any single
idle source, find a SET of sources whose arrivals cluster within 1–2
turns of each other and whose combined ships ≥ defender garrison ×
overkill margin. Commit all sources in the set; mark them in mode_log.

Sketch:

```python
def _find_multi_source_wave(world, target, available, spent,
                            target_locked, max_travel, mode_log):
    # Catalog every source's solo plan (or smaller participation plan)
    candidates = []
    for src in world.my_planets:
        if mode_log.get(src.id):
            continue
        avail = _routine_avail(world, src, available[src.id] - spent[src.id])
        if avail < WAVE_PARTICIPATION_MIN:
            continue
        plan = plan_solo_capture(world, src, target, avail, max_travel)
        if plan is None:
            # Allow participation with min ships even if solo can't cap
            for try_ships in (40, 25, WAVE_PARTICIPATION_MIN):
                if try_ships > avail:
                    continue
                aim = aim_at_target(src, target, try_ships,
                                    world.initial_by_id, world.ang_vel,
                                    world=world)
                if aim is None: continue
                angle, turns = aim
                if turns > max_travel: continue
                plan = (angle, turns, try_ships)
                break
        if plan is None:
            continue
        angle, turns, ships = plan
        candidates.append((turns, ships, src, angle))

    # For each arrival-time cluster (2-turn window), check if combined
    # ships beat defender. Use earliest viable cluster (shortest
    # exposure to enemy reinforcement).
    candidates.sort(key=lambda x: x[0])
    for i, (t0, _, _, _) in enumerate(candidates):
        cluster = [c for c in candidates if c[0] - t0 <= 2]
        total = sum(c[1] for c in cluster)
        need = effective_needed_to_capture(target, t0, world)
        if total >= need * SAFETY_MARGIN:
            return cluster
    return None
```

Integration: Phase B runs in place of (or before) Phase A. For each
target sorted by PV, try `_find_multi_source_wave`. If it returns a
cluster, commit all members; otherwise fall through to Phase A
single-source for that target.

### Acceptance gates (unchanged from above)

Phase B must clear:

1. Compile + smoke OK
2. 2P preservation (4P gate ensures this by construction)
3. ≥ baseline wins on **all three** of seeds 700/800/900k, total
   Δ ≥ +6 wins / 960 games
4. No catastrophic single-(group, seat) cell collapse
5. V64_INSTRUMENT evidence: turn-75 ships launched ≥ +50% vs baseline,
   not just ±10%. The whole point is to close the 4× throughput gap.

### What NOT to do in the next iteration

- Don't re-test Phase A variants. Three iterations × 960 games of
  evidence is enough. Single-source ROI greedy is settled.
- Don't add another scoring tweak. The scoring isn't the bottleneck.
- Don't lower the Phase A safety thresholds further to "find" a win.
  The pattern of variance-dominated wins-on-easy-games is not real
  signal.
- Don't ship V65_PRODUCER_4P=1 as the default. Phase A produces no
  reliable gain.
