# v6 Parameter Tuning — Failure, then Success

Date: 2026-06-04 Australia/Sydney.

## TL;DR

Two rounds of work.

**Round 1 (failure):** Coordinate descent over 6 numeric parameters against a
frozen v5 self-play baseline. Found "winners" with up to +60pp apparent win
rate. **They all collapsed against the real opponent (public_shuming) on
fresh seeds** — combined variant lost 1/20 vs shuming. Diagnosed as
seed-specific overfitting + interaction effects + wrong target (the frozen
baseline ≠ the real opponent).

**Round 2 (success):** Switched to **feature ablations** — binary
disable-one-feature tests — directly vs the real opponent (public_shuming) on
50 games per variant. Six of seven features had no effect in 2p (mostly
4p-only features) or were noise. **One ablation reproduced:
`V124_ANTI_SNIPE=0`** — gains +4 wins / 50 on discovery (seeds 200000+) and
+2 wins / 50 on validation (seeds 300000+) vs shuming. Cross-checked vs
lb1039 (28/30 → 28/30, neutral) and ajay (17/30 → 17/30, neutral).
**Promoted to main.py** by flipping the default of the existing
`V124_ANTI_SNIPE` env var from "1" to "0".

Submitted artifact: `main.py` v6.1, identical to v5 except
`ANTI_SNIPE_ENABLED` defaults to False.

The full process for both rounds is documented below — including the
mistakes — so the next person doesn't make the same ones.

## The goal

v5 hit ~70% win rate vs public_shuming on early benchmark seeds. The next
step from [strategy_gap_analysis.md](strategy_gap_analysis.md) #10 — full
RL/self-play — is weeks of work. The adjacent practical path is automated
parameter tuning: shuming has dozens of tuned constants set by its public
author at some point in time, against the public field at that time. We can
plausibly find values better suited to current opposition.

## Exact process

### Step 1 — Expose parameters as env vars

Edited [main.py](../main.py) to wrap selected constants in
`os.environ.get(...)` reads with the prior values as defaults. Convention:
`TUNE_<NAME>`. Wrapped:

- `HAMMER_STOCKPILE_MIN` → `TUNE_HAMMER_STOCKPILE_MIN`
- `HAMMER_PROD_SHARE_TRIGGER` → `TUNE_HAMMER_PROD_SHARE`
- `HAMMER_OVERKILL_RATIO` → `TUNE_HAMMER_OVERKILL`
- `VALUE_WEIGHT_2P` → `TUNE_VALUE_WEIGHT_2P`
- `F1B_EXPAND_BONUS` → `TUNE_EXPAND_BONUS`
- `SO1_STATIC_BONUS_2P` → `TUNE_STATIC_BONUS_2P`
- All 5 entries of `MODE_PARAMS_2P["pressure"]` →`TUNE_2P_PRESS_*`

**Trap #1.** Three of those (`HAMMER_STOCKPILE_MIN`, `HAMMER_PROD_SHARE_TRIGGER`,
`HAMMER_OVERKILL_RATIO`) are GLOBAL fallback defaults that get OVERRIDDEN by
mode-specific values from `world.mode_params[...]` at runtime. In 2p the active
mode is `pressure` after opening, so the hot value is
`MODE_PARAMS_2P["pressure"]["hammer_overkill"]`, not the global. Verified by
grep + reading the code. **Tuning the global has zero effect in 2p.** First
sweep wasted ~80 games before I noticed all three variants returned identical
results.

### Step 2 — Subprocess-isolated harness

Wrote [tools/match_runner.py](../tools/match_runner.py): plays a single 2p
match (variant vs opponent at chosen seat) and emits one JSON line
`{status, margin, scores, rewards}`.

Wrote [tools/tune.py](../tools/tune.py): given `--multi KEY=v1,v2,...`,
generates the Cartesian product of variants. For each variant: spawns
match_runner.py in a fresh subprocess with `TUNE_*` env vars applied. Runs
`2 × games` matches per variant (both seats) and reports aggregate
wins/ties/losses/avg_margin.

**Why subprocess.** main.py reads env vars at module-import time. Once
loaded, the constants are baked in — `importlib.reload` won't even update
module-level constants. A fresh subprocess per match is the cleanest
isolation.

### Step 3 — Frozen-baseline reference

[baselines/main_v5_baseline.py](../baselines/main_v5_baseline.py) is a copy
of main.py with **all `TUNE_*` env reads literally rewritten to the default
value** (used a Python regex pass). So when the variant subprocess sets
`TUNE_X=Y`, the baseline copy in the same process still plays with the v5
defaults. Verified `grep -c TUNE_` → 0.

### Step 4 — Individual parameter sweeps (round 1)

Each parameter swept across 4-5 values × 10 seeds × 2 seats = 20 games,
opponent = frozen v5 baseline.

#### TUNE_2P_PRESS_HAMMER_OK (mode-specific hammer overkill)

Sweep `1.12, 1.18, 1.25, 1.32, 1.40` on seeds 40000-40003 (8 games each):

| value | wins | margin |
|---|---|---|
| 1.18 (default 1.177645) | 6/8 | +453 |
| 1.40 | 4/8 | -289 |
| 1.25 | 2/8 | -1469 |

Default holds. (Discovered 1.25 is actively bad — useful trap data even though
no improvement.)

#### TUNE_VALUE_WEIGHT_2P (offensive scoring weight)

Sweep `4.0, 4.86, 5.5, 6.5, 7.5` on seeds 60000-60009 (20 games each):

| value | wins | margin |
|---|---|---|
| **6.5** | **16/20 (80%)** | **+1125** |
| 7.5 | 15/20 | +995 |
| 5.5 | 13/20 | +586 |
| 4.0 | 13/20 | +498 |
| 4.86 (default) | 10/20 | +14 |

**APPARENT** big win. Default 4.86 → 6.5 looked like +60 percentage points of
winrate.

Narrow sweep `6.0-7.0` on seeds 70000-70009 confirmed 6.0-7.0 plateau around
60-70% win vs baseline.

#### TUNE_EXPAND_BONUS

Sweep `1.5, 2.5, 3.0, 4.0, 5.0` on seeds 60000-60009:

| value | wins | margin |
|---|---|---|
| 1.5 | 13/20 (65%) | +587 |
| 3.0 (default) | 10/20 | 0 |
| 5.0 | 7/20 | -777 |

Apparent winner: 1.5. Lower bound sweep `0.5,1.0,1.5,2.0` on seeds 70000-70009
showed all 4 values at 8/20 wins — essentially flat. Decided 1.5 was "the
winner".

#### TUNE_STATIC_BONUS_2P

Sweep `1.5, 2.18, 3.0, 4.0` on seeds 60000-60009:

| value | wins | margin |
|---|---|---|
| **3.0** | **14/20 (70%)** | **+804** |
| 2.18 (default) | 10/20 | 0 |

Apparent winner: 3.0.

#### TUNE_2P_PRESS_EXPAND_K_OPEN × _MID joint

9 cells. `EXPAND_K_OPEN` had **zero effect** — same MID gave identical
results across OPEN ∈ {3,5,7}. (Real signal: that param isn't on the hot
path in our matches.) `EXPAND_K_MID=2` (default) was optimal vs 4 and 6.

### Step 5 — Round 2: combine the winners

Combined variant
`{VALUE_WEIGHT_2P=6.5, EXPAND_BONUS=1.5, STATIC_BONUS_2P=3.0}` tested two ways:

**Vs frozen v5 baseline, fresh seeds 80000-80014 (30 games):**

```
wins=14  ties=0  losses=16  win_rate=0.47  avg_margin=-335
```

Not a win. Essentially even/slightly worse.

**Vs public_shuming, seeds 90000-90009 (20 games):**

```
wins=1  ties=0  losses=19  win_rate=0.05  avg_margin=-1837
```

**Catastrophic.** 5% win rate vs shuming.

### Step 6 — Diagnose: was it the combination, or the individual choices?

Re-tested each individual parameter vs **public_shuming** (the real opponent,
not the frozen baseline) on the fresh seed range 90000-90009 (20 games each):

| variant | wins vs shuming | margin |
|---|---|---|
| Default `VW=4.86` | 5/20 (25%) | -879 |
| "Winner" `VW=6.5` | **2/20 (10%)** | **-1527** |
| Default `EB=3.0` | 5/20 (25%) | -879 |
| "Winner" `EB=1.5` | 5/20 (25%) | -903 |
| Default `SB=2.18` | 5/20 (25%) | -879 |
| "Winner" `SB=3.0` | 6/20 (30%) | -712 |

So:
- **VALUE_WEIGHT_2P=6.5 is provably worse than default** on a fresh seed
  range. Lost 18/20 vs default's 15/20.
- **EXPAND_BONUS=1.5 is essentially identical to default** — 5/20 either way.
- **STATIC_BONUS_2P=3.0 is marginally better** — +1 win, ~+170 margin. But
  one extra win in 20 is well inside the noise floor.

The 80% win rate of `VW=6.5` against the frozen baseline on seeds 60000+ was
**seed-specific noise**, not a real improvement.

## Why this happened (lessons)

1. **Per-seed variance is enormous.** Even the SAME bot (current main.py with
   defaults) wins 5/6 (83%) vs shuming on seeds 10000-10002 in the v5
   benchmark, but only 5/20 (25%) on seeds 90000-90009. Same agent, 3x
   different win rate. 20 games per variant is not enough to overcome this.

2. **Apples-to-apples baseline ≠ real opponent.** The frozen v5 baseline is a
   weaker target than shuming itself — variants that exploit symmetric
   mirror-match-with-tweak weaknesses can look great vs the baseline and
   collapse vs a genuinely different opponent.

3. **Coordinate descent ignores interactions.** Three apparent +10pp each can
   combine to a -15pp net effect.

4. **The opponent matters.** Tuning vs `main_v5_baseline` selected for
   parameters that beat the v5-shaped opponent, not for parameters that
   generalize. The Kaggle ladder has many opponent types.

5. **Dead defaults waste cycles.** Three of my initial param hooks
   (`HAMMER_STOCKPILE_MIN`, `HAMMER_PROD_SHARE_TRIGGER`, `HAMMER_OVERKILL_RATIO`)
   were never actually used in 2p — the mode-params dict overrides them at
   runtime. Should have read the call sites before exposing env vars.

## Round 2 — feature ablations, vs the real opponent, on held-out seeds

After the round-1 failure I changed approach in three ways:

1. **Binary disable-one-feature ablations**, not numeric sweeps. Higher
   signal-to-noise — a feature that meaningfully changes play will swing
   results more than a 30% tweak to a continuous parameter.
2. **Opponent = public_shuming directly**, not the frozen baseline. The
   frozen baseline doesn't represent the real ladder.
3. **Larger samples** (50 games per variant) plus **a separate validation
   seed range**. Promote only if a variant beats baseline on BOTH the
   discovery range AND the validation range.

### Discovery sweep — seeds 200000-200024, 50 games each

Tested each ablation as `--multi V12X_FEATURE=0`. The 7 features picked are
the ones shuming exposed via env vars in the first place — they're the
mostly-recent additions where the author was least sure of the value.

| Variant | Wins / 50 | Margin |
|---|---|---|
| **Default (baseline)** | **20/50 (40%)** | -484 |
| `V124_ANTI_SNIPE=0` | **24/50 (48%)** | -183 |
| `V128_NEUTRAL_CAP=0` | 22/50 (44%) | -361 |
| `V128_LEADER_BASH=0` | 20/50 | -484 |
| `V128_TEMPO_FILTER=0` | 20/50 | -484 |
| `V128_WEAKEST_TARGET=0` | 20/50 | -484 |
| `V128_ENDGAME_ROI=0` | 20/50 | -484 |

Five of seven returned **identical** results to baseline. Three of those
are 4p-only features (`V128_LEADER_BASH`, `V128_WEAKEST_TARGET`,
`V124_CHEAP_PICKUP`) — they're gated behind `if not world.is_2p` so they
never fire here. Two more (`V128_TEMPO_FILTER`, `V128_ENDGAME_ROI`) are
late-game features that didn't trigger at the cadence to swing wins. Good
signal: those features can't be the lever in 2p.

`V124_ANTI_SNIPE=0` was +4 wins, +300 margin. `V128_NEUTRAL_CAP=0` was
+2 wins, +120 margin. Possible signal.

### Validation sweep — seeds 300000-300024, 50 games each

| Variant | Wins / 50 | Margin |
|---|---|---|
| Default (baseline) | 24/50 (48%) | -93 |
| **`V124_ANTI_SNIPE=0`** | **26/50 (52%)** | **-39** |
| `V128_NEUTRAL_CAP=0` | 22/50 (44%) | -256 |
| Combined (both = 0) | 24/50 (48%) | -191 |

`V124_ANTI_SNIPE=0` **reproduced**: +2 wins / 50 on validation, in the same
direction as discovery (+4 / 50). Two seed ranges, both positive — real.

`V128_NEUTRAL_CAP=0` **did NOT reproduce**: +2 on discovery, −2 on
validation. Within seed variance. **Noise.**

Combined variant matched baseline (24/50) — the two changes cancel each
other (consistent with `NEUTRAL_CAP=0` being neutral and bringing back the
baseline behavior).

### Cross-opponent check — seeds 400000-400014, 30 games each

Made sure the `V124_ANTI_SNIPE=0` change doesn't hurt vs other publics:

| Opponent | Default | `V124_ANTI_SNIPE=0` | Verdict |
|---|---|---|---|
| public_lb1039 | 28/30 (93%, +2301) | 28/30 (93%, +1747) | neutral |
| public_ajay12 | 17/30 (57%, +387) | 17/30 (57%, +316) | neutral |

Identical win count vs both, slightly lower margins. Promotion is safe.

### Final public benchmark — seeds 500000+

```text
python tools/benchmark.py --suite public --games 3 --seed-start 500000

2p_v3            6/6  margin +2831
2p_lb1039        6/6  margin +2831
2p_lb1224        6/6  margin +3522
2p_shuming       3/6  margin   +243
2p_ajay          3/6  margin   +173
TOTAL 2p        24/30 (80%)

4p_pub_mixed     4/12 (33%)
```

Consistent with v5 (was 25/30 in 2p). Specific shuming/ajay matchups are
within seed variance of v5's results. The ablation's real signal is in the
50-game studies above, not in 6-game shuming bench cells.

## Promotion

The single change applied to `main.py`:

```diff
-ANTI_SNIPE_ENABLED = os.environ.get("V124_ANTI_SNIPE", "1") != "0"
+ANTI_SNIPE_ENABLED = os.environ.get("V124_ANTI_SNIPE", "0") != "0"
```

Header comment in `main.py` updated to `v6.1`. The `V124_ANTI_SNIPE`
environment variable still lets a user reverse this if needed
(`V124_ANTI_SNIPE=1` restores the v5 behavior).

## What's on disk

- [main.py](../main.py): v6.1, `ANTI_SNIPE_ENABLED` defaults to False.
  All other TUNE_*/V12{4,8}_* env hooks present but inactive without
  overrides.
- [baselines/main_v5_baseline.py](../baselines/main_v5_baseline.py): frozen
  v5 reference for future apples-to-apples testing.
- [baselines/our_v3.py](../baselines/our_v3.py): pre-v5 (1039-style) main.
- [tools/match_runner.py](../tools/match_runner.py),
  [tools/tune.py](../tools/tune.py): reusable harness.
- All sweep results: `notes/{tune,abl,val}_*.json`.

## What to try next, with discipline

1. **More games per variant.** 50-100 games minimum per parameter value, not
   20. Cuts the runtime budget per sweep but produces real signal.

2. **Validate on FRESH seeds.** Sweep on seeds A, validate the winner on seeds
   B before promoting. Add this as a hard rule to `tune.py`.

3. **Always test vs the real opponent (public_shuming), not just self-play.**
   The frozen baseline is useful for fast iteration but not a sufficient
   acceptance gate.

4. **Hold out a "validation gauntlet"** — a fixed set of seeds + opponent mix
   that the variant must beat before promotion. The current
   `tools/benchmark.py --suite public` is close to this.

5. **For each candidate change, ask: does the variant beat shuming on FRESH
   seeds by ≥ 3 wins out of 20?** Anything less is noise.

6. **Bayesian / population-based tuning** beats coordinate descent on noisy
   objectives. If we go further down this road, use that.

7. **The real next path remains RL/self-play** (strategy_gap_analysis.md #10).
   This was a worthwhile detour that confirms: heuristic parameter tuning on
   top of a maturely-tuned codebase like shuming is unlikely to yield big
   gains without much larger sample sizes.

## Submit command

```bash
kaggle competitions submit orbit-wars -f main.py -m "v6.1 anti-snipe off"
```

## 2026-06-04 4P patchnotes — v6.1 is cracked in FFA

Follow-up after the live submission started bleeding rating in 4-player games.

### Live leaderboard snapshot

Full public leaderboard download at `2026-06-04T02:36:16Z`:

- `JosephMontana`: rank **389**, score **1064.5**.
- Top 10 range: **1533.1-1678.4**.
- Top 5: TonyK 1678.4, Jake Will 1660.2, 213tubo 1624.9,
  typeIIIfairy 1605.3, Zachary Ruhe 1601.4.

Top-of-board recheck later on 2026-06-04:

- Top 4: Jake Will 1672.3, TonyK 1666.1, 213tubo 1616.9,
  Zachary Ruhe 1606.5.
- Zachary Ruhe has no rows in the public top-20 replay parquet dataset checked
  below, so we can compare the other three current top-4 names but should not
  invent Zachary-specific behavior from this data.

`kaggle competitions submissions orbit-wars` still shows submitted artifact
`53344833` as `v6.1 anti-snipe off` with public score 1077.8 at completion.
The full leaderboard has already drifted lower, so use the leaderboard
download for current rank/score.

### Replay evidence from our latest submission

Downloaded all 21 public episodes for submission `53344833`:

- Overall: **11-10**.
- 2P: **8-1**.
- 4P: **3-9**.

The 4P losses split into:

- 2 losses classified as out-expanded by turn 50.
- 2 losses classified as out-expanded by turn 75.
- 5 losses classified as combat/endgame collapse.

4P aggregate, us vs eventual winners:

| Metric | Us | Winners |
|---|---:|---:|
| First action turn | 5.33 | 3.75 |
| Turn 50 production | 12.08 | 16.92 |
| Turn 50 score | 175.75 | 249.25 |
| Turn 75 production | 14.33 | 20.50 |
| Turn 75 score | 211.58 | 451.83 |
| Turn 75 active fleets | 2.50 | 6.25 |
| Turn 100 production | 15.42 | 25.17 |
| Turn 100 score | 288.92 | 645.42 |

Conclusion: this is not a generic agent failure. It is specifically a 4P macro
failure. v6.1 is still strong enough in 2P, but in 4P it either falls behind
economically before turn 75 or reaches parity and then lacks enough active fleet
mass to survive the midgame.

### Public high-end evidence

Direct code/episodes for the current top leaderboard bots are not exposed by
the leaderboard row. `kaggle competitions episodes <top team id>` returns no
episodes; team id is not submission id. Do not pretend we can inspect TonyK or
Jake Will code from the leaderboard.

Closest public evidence checked:

- Full leaderboard top names/scores, as above.
- Kaggle public notebooks:
  - `slawekbiel/the-producer-agent`
  - `shummingfang/orbit-wars-exp34`
  - `ajayrao43/orbit-war-121`
- Public top-replay dataset:
  `nbridelancetb/orbit-wars-replay-parquet`, 4,992 total episodes, 934 4P
  games from top leaderboard players as of May 2026.

Top-replay 4P winners average:

| Metric | Top-replay 4P winners |
|---|---:|
| First action turn | 4.13 |
| First expansion turn | 10.55 |
| Actions by turn 25 | 5.89 |
| Ships launched by turn 25 | 120.65 |
| Turn 50 production | 18.64 |
| Turn 75 production | 26.11 |
| Turn 75 score | 518.30 |
| Turn 75 active fleets | 6.45 |

Our 4P sample is below this winner profile by turn 50 and very far below it by
turn 75. The key gap is not only target quality; it is launch volume, active
fleet mass, and keeping production growth alive after the opening.

### What public bots appear to do

Producer-style public bot:

- Scores source-target candidates by projected production ROI.
- Uses `safe_drain` / max-source launch sizing, not just minimum-needed ships.
- Greedily selects up to 6 waves per turn above a score threshold.
- Has a 4P preset with shorter horizon and fewer sources/defense targets.
- Regroups unused ships toward pressure/frontline gradients.

Shuming/exp34-style public bot:

- Search expansion in 4P.
- Leader-bash and weakest-enemy targeting.
- Stop-expansion gates for combat, production lead/lag, neutral saturation,
  stockpiling, and late-game ROI.
- Accumulator: safe backline planets feed a lead stockpile.
- Mega-hammer: one huge fleet from the lead stockpile.
- Persistent hammer plans with synchronized stockpile fleets.

Current `main.py` already contains most Shuming-style machinery, but the latest
promotion validated almost everything in 2P. The 4P problem is likely gating,
activation, and tuning, not absence of a named subsystem.

### What top-bot replays do differently

Deeper pass over the public top-20 replay parquet dataset, plus raw samples:

- TonyK win `77242833`
- Jake Will win `77249445`
- Vincent Schuler win `77162062`
- 213tubo win `77175850`

The most important difference is **snowball reinvestment after the first
capture**, not merely the first launch. Our first expansion turn in latest 4P
games is close to top replays (10.50 vs top-winner 10.55), but after that the
top bots turn captured production into fleet traffic much faster.

4P cohort comparison:

| Metric | Top-20 winners | Current top-score name wins | Best 4P-WR name wins | Our 4P | Our 4P losses |
|---|---:|---:|---:|---:|---:|
| First action | 4.13 | 4.11 | 4.11 | 5.33 | 5.33 |
| First expansion | 10.55 | 10.26 | 10.47 | 10.50 | 10.56 |
| Actions turns 0-25 | 5.90 | 5.56 | 5.18 | 3.76 | 4.11 |
| Ships launched turns 0-25 | 120.65 | 123.21 | 109.58 | 65.67 | 72.90 |
| Production at 20 | 9.22 | 9.39 | 9.30 | 5.92 | 6.11 |
| Production at 50 | 18.64 | 17.76 | 18.48 | 12.08 | 12.11 |
| Production at 75 | 26.11 | 25.07 | 25.85 | 14.33 | 12.44 |
| Planets at 75 | 9.23 | 8.89 | 9.16 | 5.25 | 4.78 |
| Active fleets at 75 | 6.45 | 6.44 | 4.95 | 2.50 | 2.11 |
| Fleet share at 75 | 0.46 | 0.49 | 0.42 | 0.26 | 0.23 |
| Ships launched turns 26-50 | 489.33 | 555.95 | 434.78 | 187.42 | 200.56 |
| Ships launched turns 51-75 | 1007.31 | 1107.81 | 925.14 | 288.83 | 255.56 |
| Avg launch size turns 51-75 | 45.49 | 49.06 | 48.92 | 29.62 | 27.95 |
| Max launch size turns 51-75 | 121.19 | 130.74 | 120.00 | 55.25 | 56.67 |

Capture profile:

| Metric | Top-20 winners | Current top-score names | Best 4P-WR names | Our 4P | Our 4P losses |
|---|---:|---:|---:|---:|---:|
| Captures by 20 | 1.99 | 1.88 | 1.98 | 1.50 | 1.67 |
| Captures by 50 | 6.90 | 6.03 | 6.39 | 4.67 | 5.11 |
| Captured production by 50 | 20.85 | 18.37 | 19.52 | 12.67 | 13.22 |
| High-prod captures by 50 | 4.19 | 3.70 | 3.92 | 2.33 | 2.44 |
| Captures by 75 | 13.40 | 11.50 | 11.79 | 9.00 | 9.44 |
| Captured production by 75 | 37.78 | 32.33 | 33.30 | 23.00 | 22.89 |

Raw replay shape:

- TonyK `77242833`: first action turn 1, production **34** at turn 50,
  **47** at turn 75, score **913** at turn 75. Takes multiple prod-4 planets
  by turn 30 and keeps 40-60 ship attacks flowing.
- Jake Will `77249445`: production **28** at turn 50, **53** at turn 75,
  fleet ships **491** at turn 75. Opening is not just neutral expansion; new
  captures are immediately used as launch platforms.
- Vincent Schuler `77162062`: production **40** at turn 50, **63** at turn 75,
  active fleets **47** at turn 100. This is a high-throughput pressure style.
- 213tubo `77175850`: extreme spam/throughput style; production **69** at turn
  75 with **152** active fleets. Not necessarily the style to copy wholesale,
  but it shows that top 4P bots are comfortable keeping almost all useful ships
  in motion.

Current top-4 leaderboard names vs our 4P losses:

| Metric | Jake Will wins | TonyK wins | 213tubo wins | Zachary Ruhe | Our 4P losses |
|---|---:|---:|---:|---:|---:|
| Public replay rows | 50 | 51 | 23 | 0 | 9 |
| First action | 4.02 | 3.78 | 4.17 | n/a | 5.33 |
| First expansion | 10.88 | 10.04 | 11.61 | n/a | 10.56 |
| Ships launched turns 0-25 | 108.52 | 114.35 | 117.39 | n/a | 72.89 |
| Production at 50 | 15.70 | 18.18 | 18.13 | n/a | 12.11 |
| Production at 75 | 22.54 | 25.02 | 28.00 | n/a | 12.44 |
| Planets at 75 | 7.94 | 8.37 | 9.83 | n/a | 4.78 |
| Active fleets at 75 | 3.86 | 4.76 | 15.52 | n/a | 2.11 |
| Fleet share at 75 | 0.47 | 0.42 | 0.53 | n/a | 0.23 |
| Ships launched turns 26-50 | 429.82 | 493.43 | 552.61 | n/a | 200.56 |
| Ships launched turns 51-75 | 909.30 | 991.06 | 1279.87 | n/a | 255.56 |
| Avg launch size turns 51-75 | 64.44 | 54.38 | 42.41 | n/a | 27.95 |
| Max launch size turns 51-75 | 141.30 | 121.39 | 114.00 | n/a | 56.67 |
| Captures by 50 | 5.88 | 6.31 | 6.96 | n/a | 5.11 |
| Captured production by 50 | 17.80 | 19.84 | 21.57 | n/a | 13.22 |
| Captures by 75 | 11.18 | 13.25 | 14.17 | n/a | 9.44 |
| Captured production by 75 | 32.16 | 39.96 | 40.26 | n/a | 22.89 |

How the current top-4-style gap reads:

- **Jake Will:** not extremely spammy by fleet count, but sends much larger
  midgame fleets than us. The big contrast is launch quality and payload:
  64.44 average ships per turn-51-75 launch vs our 27.95.
- **TonyK:** strong compounding profile. Similar first expansion timing, but
  more high-value production captured by turns 50-75 and about 4x our
  turn-51-75 launch volume.
- **213tubo:** high-throughput pressure style. By turn 75 in wins, it averages
  15.52 active fleets and 53% of ships in flight. This is the clearest example
  that our 4P losses are too static.
- **Zachary Ruhe:** currently top 4 on the live leaderboard, but absent from
  the public replay parquet sample. Need replays or public code before making
  a specific claim.

Practical interpretation:

1. **We are too slow to compound.** First expansion is fine; second/third/fourth
   profitable captures are late or too low-production.
2. **We under-launch after turn 25.** Top winners launch about 2.6x our ships
   during turns 26-50 and about 3.5x our ships during turns 51-75.
3. **Our fleet sizes stay too small in losses.** Top winner midgame launches
   average ~45-49 ships with max per-game launches around 120-130; our losses
   average ~28 with max around 57.
4. **We hold too much mass on planets in 4P losses.** Top winners have ~46-49%
   of ships in flight at turn 75; our losses have ~23%.
5. **Top bots prioritize high-production captures.** By turn 50, top winners
   have about 4 high-prod captures and 20.85 captured production; our losses
   have about 2.44 high-prod captures and 13.22 captured production.

This points toward fixing 4P expansion/reinvestment and midgame launch
throughput before exotic tactics. The agent needs to take more prod-3/4/5
targets early, immediately use new holdings as sources, and shift from
routine neutral picking into higher-throughput pressure by turns 25-50.

### v6.2 implementation result

Implemented in [main.py](../main.py) as a conservative 4P-only default:

- Broaden 4P search expansion from `3` candidates/source, `12` evaluated,
  `5` picked to `5` candidates/source, `28` evaluated, `7` picked.
- Sort 4P search candidates before expensive evaluation by production,
  enemy-vs-neutral, arrival turn, then distance.
- Raise `VALUE_WEIGHT_4P` default from `2.0` to `3.5`.
- Keep 4P depth-2 penalty off by default via `V62_SEARCH_DEPTH2_4P=0`; the
  2P depth-2 path remains unchanged.
- Add, but do not default-enable, two pressure experiments:
  `V62_4P_PAYLOAD_PRESSURE=1` for larger midgame payload sizing, and
  `V62_4P_COMPOUND=1` for an idle-source pressure pass.

Local A/B summary:

| Config | Seed slice | Result |
|---|---|---:|
| Final default v6.2 | public benchmark, seed 600000 | 4P 2-2, avg margin +121.0 |
| Old-behavior toggle | public benchmark, seed 600000 | 4P 2-2, avg margin -28.8 |
| Final default v6.2 | 4P gauntlet, seed 610000, 2 groups | 4-4, avg margin -9894.4 |
| Old-behavior toggle | 4P gauntlet, seed 610000, 2 groups | 2-6, avg margin -10752.0 |
| Payload pressure on | 4P gauntlet, seed 610000, 2 groups | 0-8, avg margin -16533.5 |
| Old search + payload pressure | 4P gauntlet, seed 610000, 2 groups | 0-8, avg margin -16345.2 |
| Idle-source pressure pass | public 4P group, seed 600000 | 0-4, avg margin -8403.5 |

Verification:

```bash
python -m py_compile main.py
python tools/benchmark.py --suite public --games 1 --seed-start 600000
python tools/gauntlet.py --suites 4p --games 1 --seed-start 610000 --max-4p-groups 2
```

Final public benchmark with v6.2 defaults produced no errors. The 2P rows
matched the prior smoke, while 4P finished 2-2 on the seed-600000 public
benchmark and 4-4 on the bad seed-610000 4P gauntlet.

### What NOT to do next

1. **Do not promote 2P-only evidence globally.** `V124_ANTI_SNIPE=0` was
   validated against 2P public Shuming/Ajay-class opponents, but it changes 4P
   behavior too. This is the most suspicious v6.1 process mistake.

2. **Do not trust aggregate win rate.** The latest sample is 11-10 overall and
   still bad, because 2P hides the 3-9 4P leak. All future reports must split
   2P and 4P.

3. **Do not chase top leaderboard code.** Current top bots are private. Use
   public notebooks and replay datasets for behavioral targets.

4. **Do not tune constants without activation counters.** If accumulator,
   mega-hammer, hammer, cheap-pickup, leader-bash, or anti-snipe almost never
   fire in 4P losses, parameter sweeps on their constants are cargo cult.

5. **Do not keep spending into slow neutrals once the 4P board is hot.** In
   losses we often have low active fleet count by turn 75. Slow neutral capture
   attempts that do not convert into production or fleet pressure are dead
   weight.

6. **Do not assume `SEARCH_DEPTH2_ENABLED=True` is a 4P win.** It was borrowed
   for 2P counter-snipe behavior. Public exp34 has it off; test 4P separately.

7. **Do not enable payload pressure from one good seed.** It improved the
   seed-600000 margin, then collapsed to 0-8 on seed 610000. The top replay
   lesson is "increase productive throughput", not "send bigger fleets
   everywhere".

8. **Do not add an idle-source pressure pass without a safety model.** The
   first version overcommitted idle sources and erased the existing public
   benchmark wins. Any future version needs timeline defense/arrival safety,
   not just production-weighted greed.

### What to do next

1. **Add a 4P acceptance harness.** A candidate is not submit-worthy unless it
   reports 2P and 4P separately and beats v6.1 on a fixed 4P replay/local
   gauntlet. Minimum macro targets from the top-replay dataset:
   turn-25 launches >= 5 actions / 100 ships, turn-50 production >= 18,
   turn-75 production >= 24, turn-75 active fleets >= 5.

2. **Instrument feature activation.** Add a debug/analysis mode that counts
   `mode_log` outcomes per replay: `search-expand`, `expand-solo`,
   `expand-coalition`, `cheap-pickup`, `accumulator-feeder`,
   `mega-hammer-launched`, `hammer`, `defense`, `doom-evac`, and anti-snipe
   vetoes. Run it on the 9 latest 4P losses.

3. **Run 4P-only ablations before the next submission.** First candidates:
   make anti-snipe mode-gated and test 4P-on / 2P-off, test
   `SEARCH_DEPTH2_ENABLED=False` for 4P only, test
   `SEARCH_DISABLES_CHEAP_PICKUP=False`, and sweep `V126_VALUE_WEIGHT_4P`.

4. **Fix low-launch openings.** In losses like episode `78675153`, we waited
   until turn 17 while the winner launched on turn 2. Add an opening-macro test
   that flags first action > 5, fewer than 4 actions by turn 25, or fewer than
   80 ships launched by turn 25 on 4P boards.

5. **Tune stop-expand gates against 4P.** The goal is not endless expansion;
   it is reaching the top-replay winner band by turn 50 and still having active
   fleets by turn 75. Test stronger stop/redirect behavior when production is
   lagging or combat contact begins.

6. **Consider a Producer-style planner as the next architecture experiment.**
   The public Producer bot is not a drop-in single-file agent because it depends
   on `orbit_lite`, but the idea is clear: score max-drain candidate waves by
   projected production ROI, greedily pick several per turn, then regroup
   leftovers toward pressure.

## 2026-06-04 v6.2 held-out validation — revert

Followed the "What to do next" #3 plan: validated v6.2 defaults on fresh seeds
700000 and 800000 before any further work could stack on top of an unproven
base.

### Setup

Added `V62_SEARCH_ORDER_4P` env var (default "0" after revert) so the prod-sort
in `search_step_action` can be toggled — previously the sort was unconditional
once `is_2p=False`, blocking a clean v6.1 revert via env vars alone.

A/B harness: `tools/gauntlet.py --suites 4p --opponents public` for the
5-group spread, then `--opponents public_lb1039,public_shuming,public_ajay` to
target only the matchup where v6.2 had any signal on seed 700000.

### Results

| Run | v6.2 wins | v6.1 wins | Δ wins | v6.2 margin | v6.1 margin |
|---|---:|---:|---:|---:|---:|
| seed 700000, 5 groups × 4 seats × 4 games (80) | 32 | 30 | +2 | -3838 | -3772 |
| seed 800000, group E × 4 seats × 20 games (80) | 20 | 21 | -1 | -1753 | -1786 |
| Combined | 52 | 51 | +1 | -- | -- |

Per-group breakdown of the seed-700000 run:

| 4P group | v6.2 | v6.1 |
|---|---:|---:|
| lb1039+lb1224+shuming | 4 | 4 |
| lb1039+lb1224+ajay | 4 | 4 |
| lb1039+lb1224+evogen | 7 | 7 |
| lb1039+lb1224+rahul | 12 | 12 |
| **lb1039+shuming+ajay** | **5** | **3** |

All seed-700000 signal was localized to group E (shuming+ajay). The targeted
seed-800000 run on the same group reversed direction: v6.2 lost 1. Net over
160 games: +1 win, well below the prompt's "+3 wins on 20 games" noise floor.

### Decision: revert v6.2 to v6.1 defaults

The v6.2 hypothesis (broader 4P search + higher VALUE_WEIGHT_4P + prod-sort
candidate ordering) does not generalize. This is the same pattern as the
round-1 coordinate descent overfit. Reverted via main.py edits:

| Env var | Before (v6.2) | After (v6.1) |
|---|---|---|
| `V62_SEARCH_MAX_PER_SOURCE_4P` | 5 | 3 |
| `V62_SEARCH_EVAL_4P` | 28 | 12 |
| `V62_SEARCH_PICK_4P` | 7 | 5 |
| `V62_SEARCH_ORDER_4P` | "1" | "0" |
| `V126_VALUE_WEIGHT_4P` | 3.5 | 2.0 |

All env vars are still wired; setting them to the v6.2 values reproduces the
old behavior. The header comment in [main.py](../main.py) is back to v6.1.

### Sample-size lesson reiterated

8-game discovery slice → +2 wins.
80-game seed 700000 → +2 wins (4 of 5 groups identical, 1 group +2).
80-game targeted seed 800000 → -1 wins.

Same effect size in absolute terms across very different sample sizes is the
signature of noise, not signal. A real +25% improvement should scale; +2/8 →
+2/80 → -1/80 is consistent with a true delta of ~0.

### Next-best held-out hypothesis to test

The throughput data still says we need more launches per turn in 4P midgame.
The single chained-launch pathway in the codebase is `handle_cheap_pickup`,
currently disabled in 4P via `SEARCH_DISABLES_CHEAP_PICKUP=True`. Re-enabling
cheap-pickup in 4P is one of the explicit untested items in "What to do next"
#3. It directly attacks the active-fleets-at-75 gap without changing target
selection or fleet sizing, and it's a binary toggle, so the ablation is clean.
Test next.

### What's on disk

- [main.py](../main.py): v6.1 defaults restored; v6.2 env vars still wired for
  future experiments.
- [notes/val_v62_4p_700k.csv](val_v62_4p_700k.csv): v6.2 defaults, 5-group 4P
  gauntlet at seed 700000.
- [notes/val_v61_revert_4p_700k.csv](val_v61_revert_4p_700k.csv): paired v6.1
  revert at same seeds.
- [notes/val_v62_groupE_800k.csv](val_v62_groupE_800k.csv): v6.2 targeted at
  lb1039+shuming+ajay, seed 800000, 80 games.
- [notes/val_v61_groupE_800k.csv](val_v61_groupE_800k.csv): paired v6.1
  targeted at the same matchup.
- [notes/val_v62_2p_700k.csv](val_v62_2p_700k.csv): 2P preservation check
  (v6.2 changes are 4P-gated, so the result mirrors v6.1 — 10/24 vs
  shuming/ajay/lb1039 on seed 700000+, with the loss concentration vs
  shuming/ajay being seed-700000 variance per the round-1 lesson).

## 2026-06-04 depth-2 / cheap-pickup ablation

After reverting v6.2, ran the next two items from "What to do next" #3:

1. **`V63_DISABLE_CP_4P=0`** — re-enable cheap-pickup in 4P (the only chained
   per-source launch path in the codebase). Hypothesis: extra launches per
   turn from sources near cheap neutrals, directly addressing the
   active-fleets-at-75 gap.
2. **`V62_SEARCH_DEPTH2_4P=1`** — enable Ajay's depth-2 counter-snipe penalty
   in 4P search. Hypothesis: more cautious target selection vs strong
   opponents avoids wasted fleets.

### Setup

Added `V63_DISABLE_CP_4P` env var (default "1", keeps existing behavior).
Both ablations are 4P-only — `cheap_pickup` is already gated by
`CHEAP_PICKUP_4P_ONLY=True`, and depth-2 4P branches behind
`SEARCH_DEPTH2_4P_ENABLED` only in the `not world.is_2p` arm of
`_handle_search_expand_4p`. 2P preservation is by construction.

### Seed-700000 5-group 4P gauntlet (80 games per variant)

| Variant | Wins/80 | Margin |
|---|---:|---:|
| v6.1 baseline | 30 | -3772 |
| `V63_DISABLE_CP_4P=0` (cheap-pickup on in 4P) | **28** | -4422 |
| `V62_SEARCH_DEPTH2_4P=1` (depth-2 on in 4P) | **33** | -3402 |

Cheap-pickup re-enable: -2 wins. Worst on group E (lb1039+shuming+ajay):
3 → 1. Reverted. Hypothesis disproved — chained launches against strong
opponents leave sources too thin.

Depth-2 4P: +3 wins on 80 games, distributed across A/B/C (+1 each), neutral
on D/E. Most promising signal of the day. Triggered held-out validation.

### Depth-2 4P held-out validation

| Seed range | v6.1 baseline | depth-2 4P | Δ wins | Δ margin |
|---|---:|---:|---:|---:|
| 700000 (5-group, 80) | 30 | 33 | +3 | +370 |
| 800000 (5-group, 80) | 27 | 29 | +2 | +89 |
| 900000 (5-group, 80) | **47** | **43** | **-4** | -148 |
| Combined (240 games) | **104** | **105** | **+1** | +104 |

Per-opponent delta combined across 3 ranges (48 games per group):

| Group | Δ wins |
|---|---:|
| vs shuming | +1 |
| vs ajay | +2 |
| vs evogen | 0 |
| vs rahul | -1 |
| vs shuming+ajay | -1 |

Seeds 700000 and 800000 both showed +2/+3 wins concentrated on shuming/ajay.
Seed 900000 reversed direction (-4 wins distributed across all groups).
Seed 900000 is a generally favorable range for v6.1 (47 wins vs 30/27
elsewhere) — the kind of range where small subtle changes seem to hurt more.

### Decision: do NOT promote depth-2 4P

Two seed ranges agreed; a third reversed. Net +1 / 240 games is the same
noise-floor result as v6.2. The lesson from v6.1 round 1 holds: per-seed
variance dominates parameter-level signals at this sample size and at this
maturity of the underlying agent.

V62_SEARCH_DEPTH2_4P and V63_DISABLE_CP_4P env vars remain wired in
[main.py](../main.py); defaults stay at v6.1 behavior.

### Lessons reinforced

- **Two seed ranges is not enough.** Both v6.2 and depth-2 4P passed a
  two-range check (+5 / 160) and failed a three-range check.
- **Distributed signal across opponent groups is more believable than
  concentrated.** Depth-2's +1/+1/+1 across A/B/C on seed 700k looked better
  than v6.2's +2 concentrated on group E — but neither was reproducible.
- **Per-seed "easy/hard" variance is large.** Seed 900000 was 47/80 wins for
  v6.1, vs 30/80 and 27/80 for seeds 700/800. Future validations should aim
  for seed-range diversity over depth within one range.
- **Adding a third seed range is cheaper than tuning a subtly-wrong
  parameter.** Both runs at seed 900k took ~25 min wall clock combined.
  Compare to days of debugging a misleading promotion.

### What to try next

The 4P macro gap is real (turn-75 fleets 2.5 vs 6.45, production 14.3 vs
26.1, ships launched 256 vs 1007). But every single-parameter / single-flag
ablation tried so far has been noise. The likely conclusion is that no
single feature toggle is the lever — the 4P deficit is a property of the
overall planning algorithm.

Productive next directions:

1. **Behavior instrumentation pass.** Add `mode_log` aggregation and turn-25
   / turn-50 / turn-75 metrics to a single match runner. Run on 4P losses to
   actually see which feature is firing / not firing.
2. **Joint ablations** — test V124_ANTI_SNIPE=1 *specifically when* the 4P
   board is shuming+ajay, where the depth-2 signal was strongest. Co-vary
   features instead of toggling one.
3. **Producer-style architecture experiment** — score multi-wave candidates
   by ROI, greedy several per turn. This is a real architectural change, not
   a parameter sweep, and may break the noise-floor ceiling we're seeing.

## 2026-06-05 v6.4 instrumentation pass + brain-lead ablation

Pursued "What to try next" #1 (instrumentation) and used the result to
target the most-dormant subsystem.

### Instrumentation hooks added (in [main.py](../main.py))

Two env-gated levers, both default to current v6.1 behavior:

- `V64_INSTRUMENT=1` enables `SUBSYSTEM_INSTRUMENT_ENABLED`. The agent
  aggregates `mode_log` tags + launch volume per game and writes JSONL
  checkpoints (steps 25/50/75/100/150/200/300/499) to the path in
  `V64_INSTR_FILE` (default `v64_instr.jsonl`). Zero behavior change when
  off; ~one int compare per turn when off.
- `V64_BRAIN_LEAD_MIN_4P` sets `BRAIN_LEAD_RESERVE_MIN_SHIPS` (default
  "200" = current behavior). The variable is 4P-only via the existing
  `BRAIN_LEAD_RESERVE_4P_ONLY=True` gate.

### Activation profile — seed 700000 group E (20 4P games, lb1039+shuming+ajay)

| Subsystem | Fires in N/20 games |
|---|---:|
| search-expand | 20/20 |
| absorb | 20/20 |
| doomed | 20/20 |
| hammer | 16/20 |
| expand-coalition | ~15/20 |
| expand-solo | ~11/20 |
| accumulator-feeder | 9/20 |
| accumulator-lead | ~9/20 |
| defense/defended-by-solo | ~17/20 |
| comet-evac | ~5/20 |
| **mega-hammer-launched** | **3/20** |
| **brain-reserved-lead** | **2/20** |
| compound-pressure | 0/20 (gated off) |

By seat:

| Seat | W/L | mega-hammer | accumulator-lead |
|---|---:|---:|---:|
| 0 (1w/4l) | low | **0/5** | 3/5 |
| 1 (2w/3l) | mid | 2/5 | 2/5 |
| 2 (2w/3l) | mid | 1/5 | 4/5 |
| 3 (0w/5l) | worst | **0/5** | 0/5 |

Clear pattern: **MEGA_HAMMER never fires in the worst-performing seats**
(0/10 games across seats 0 and 3). The gate is `brain-reserved-lead`
status, which requires 200+ ships on one planet — rare in 4P throughput.
`accumulator-lead` status is set 9/20 but is **explicitly NOT in
mega-hammer's allowed source-status list**, so accumulator-managed leads
are dead-weight for mega-hammer.

Raw data: [notes/v64_4p_activation_700k.jsonl](v64_4p_activation_700k.jsonl).

### Hypothesis

Lower `BRAIN_LEAD_RESERVE_MIN_SHIPS` from 200 → 100 in 4P (via
`V64_BRAIN_LEAD_MIN_4P=100`). This matches accumulator's own threshold
(100), should fire brain-reserved-lead in ~9/20 games (the same rate
accumulator can pick a lead), and unblock more mega-hammer firings via
the brain-reserved-lead → accumulator-feed → mega-hammer chain.

### Smoke (seed 700000 group E, 20 games)

| Var | Wins/20 | Margin | brain-reserved-lead | mega-hammer-launched |
|---|---:|---:|---:|---:|
| baseline | 5 | -935 | 2/20 | 3/20 |
| V64=100 | 6 | -668 | **11/20** | **4/20** |

brain-reserved-lead jumped 2 → 11/20 as expected, but mega-hammer only
moved 3 → 4/20. The chain bottleneck isn't lead selection — it's that
mega-hammer's own threshold (`MEGA_HAMMER_SHIPS_MIN_FRESH = 200`,
`MEGA_HAMMER_THRESHOLD_BY_PROD` ranges 200-400) is rarely reached even
on a reserved lead.

### Validation (seed 700000, 80 games, 5-group spread)

| Variant | Wins/80 | Margin |
|---|---:|---:|
| v6.1 baseline | 30 | -3772 |
| V64_BRAIN_LEAD_MIN_4P=100 | 29 | -4036 |
| Δ | **-1 wins** | **-264 margin** |

Per-group delta:

| Group | V64=100 | baseline | Δ |
|---|---:|---:|---:|
| lb1039+lb1224+shuming | 5 | 4 | +1 |
| lb1039+lb1224+ajay | 4 | 4 | 0 |
| lb1039+lb1224+evogen | 5 | 7 | -2 |
| lb1039+lb1224+rahul | 11 | 12 | -1 |
| lb1039+shuming+ajay | 4 | 3 | +1 |

Mild positive vs shuming/ajay-class (+2), mild negative vs evogen/rahul
(-3). Net -1 / 80. Same noise pattern as v6.2 and depth-2 4P. **Did not
continue to seeds 800k / 900k** — per the prior discipline a candidate
needs to clear the noise floor on the first range before consuming
compute on additional ranges. -1/80 with mixed distribution is clear noise.

### Decision: keep env vars wired, defaults at v6.1

Both `V64_INSTRUMENT` and `V64_BRAIN_LEAD_MIN_4P` stay in main.py.
Defaults match v6.1. The instrumentation is the durable artifact — any
future single-parameter or joint-ablation experiment should run with
`V64_INSTRUMENT=1` to capture activation patterns directly.

### Lesson sharpened

The actual gate on mega-hammer is **MEGA_HAMMER's own threshold + status
filter**, not brain-lead selection:

```python
if status and status not in ("cheap-pickup", "brain-reserved-lead"):
    continue
```

`accumulator-lead` is conspicuously absent. Any 4P stockpile that brain
didn't pre-reserve at 200 ships is invisible to mega-hammer — accumulator
can build it up but it stays unused. Lowering brain to 100 just creates
"reserved leads that never fire mega-hammer" because the ships never
accumulate past mega-hammer's own 200-400 floor in 4P.

Two follow-up hypotheses this generates (both still single-parameter, so
expect the same noise-floor risk):

- **A. Allow `accumulator-lead` status in mega-hammer's source-status
  filter** (1-line code change). Mega-hammer can then fire from accumulator
  leads that have organically reached 200+. Should not affect 2P (4P-only
  via `MEGA_HAMMER_4P_ONLY=True`). Cleanest test of "the status filter is
  the bottleneck".
- **B. Lower `MEGA_HAMMER_SHIPS_MIN_FRESH` from 200 → 120 in 4P only.**
  Allows smaller mega-hammers from fresh captures. Risk: smaller fleets
  exploit the speed curve less and may lose tied combats. Tracks the
  top-replay finding that 4P winners launch ~45 ships per midgame wave —
  not 200+.

Both should be tested *jointly* (`A+B` toggled together) as the next
candidate, since they target the same chain. This is the "joint ablation"
direction from #2 in the prior section. Discipline: validate on
700/800/900k with held-out CSV pairs; promote only if ≥+2 wins on two
ranges and no clear regression on the third.
