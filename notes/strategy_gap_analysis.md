# Orbit Wars Strategy Gap Analysis

Last checked: 2026-06-04 Australia/Sydney.

## Current live state

- v1 `53297665`: complete, public score ~553.9 at last check.
- v2 `53299074`: complete, public score ~544.1 at last check.
- v6.1 `53344833`: complete, submitted as `v6.1 anti-snipe off`. Submission
  table showed 1077.8 at completion; full leaderboard download at
  `2026-06-04T02:36:16Z` showed rank 389, score 1064.5.
- v6.2 local patch reverted 2026-06-04 after held-out validation on seeds
  700000 (5-group 4P, 80 games) and 800000 (targeted shuming+ajay, 80 games)
  showed +1 net win across 160 games — at the noise floor. v6.2 env vars
  (`V62_*`, `V126_VALUE_WEIGHT_4P`) stay wired for future experiments but
  [main.py](../main.py) defaults are back to v6.1. See
  [v6_param_tuning_notes.md](v6_param_tuning_notes.md) "2026-06-04 v6.2
  held-out validation — revert" section.
- Current top 10 cutoff is roughly 1533 public rating; #1 is 1678.4.
- Kaggle score is a skill-rating estimate, not game-score points. It is updated from wins/losses/ties against similarly rated bots, so "3x score" does not mean "3x ships"; it means we are still near the initial/low-skill rating band while top bots consistently beat strong opponents.

## 2026-06-04 4P update

Latest submission replays show that v6.1 is not failing evenly:

- 21 downloaded public episodes: 11-10 overall.
- 2P: 8-1.
- 4P: 3-9.

4P losses are the current rating leak. By turn 75, our 4P sample averages
production 14.33, score 211.58, active fleets 2.50; eventual winners average
production 20.50, score 451.83, active fleets 6.25.

The public top-20 replay parquet dataset gives a useful target profile for 4P:
4P winners average 5.89 actions / 120.65 ships launched by turn 25,
production 18.64 by turn 50, production 26.11 and 6.45 active fleets by turn
75. Our 4P sample is below the winner profile by turn 50 and badly behind by
turn 75.

See [v6_param_tuning_notes.md](v6_param_tuning_notes.md) for the detailed
patchnotes, implementation A/Bs, "what not to do", and the next 4P experiment
list.

## Public evidence reviewed

- Public notebooks:
  - `suntzuisafteru/orbit-wars-1039-2-lb-launch-safety-heuristic`
  - `scenerysunfireink/orbit-wars-lb-1224-fork`
  - `penguin069/evogen-v5-1093`
  - `shummingfang/orbit-wars-exp30`
  - `ajayrao43/oribt-war-12`
  - `rahulchauhan016/orbit-wars-advanced-agent-target-1608-6`
- Public discussions:
  - "Some considerations on evaluating targets" discussion 699003
  - "Sharing our RL lessons so far" discussion 697725
  - "Community Benchmark - 50-Agent Mega Tournament" discussion 698614
  - Top replay dataset discussions 697413 and 701894

## Why public 1000+ bots beat us

1. **They evaluate targets by discounted value and danger, not just production / distance.**
   Public target-evaluation discussion says a present-value formula plus trajectory calculations can reach around 1000 rating. It also emphasizes local danger: nearby enemy planets can recapture a target immediately after we take it.

2. **They solve intercept geometry more carefully.**
   The 1039 notebook uses fixed-point intercept for orbiting planets, comet-path sweep, continuous collision checks, and sun safety. Our bot aims well enough for baselines but not enough for strong moving-target/comet play.

3. **They have a real defense pass.**
   Public 1039 bot has:
   - skip reserves for fleets doomed by sun or planet collision
   - skip doomed planets instead of wasting rescue ships
   - reinforce high-production planets before threats land
   Our reserve/defense logic is much simpler and does not model full arrival timelines.

4. **They send full available fleets when selected.**
   The 1039 author explicitly calls this one of the promotion deltas: solve aim using the fleet size you will actually launch, then send full available. Public agents exploit the speed curve. Our bot often sends minimum-needed fleets and loses tempo/mass.

5. **They penalize unsafe launches.**
   The 1039 launch-safety heuristic penalizes firing from front-line planets near enemy planets/fleets. v2 got worse partly because it fixed opening tempo by draining planets, but did not add equivalent launch safety.

6. **They use arrival ledgers and timeline simulation.**
   Public 1224/Shuming/Ajay agents include `simulate_planet_timeline`, `build_arrival_ledger`, `state_at_timeline`, and `forward_project`. They reason about who owns a planet at future turns after multiple arrivals. We mostly reason about one candidate at a time.

7. **They have mode-specific systems.**
   Higher public agents distinguish:
   - 2p vs 4p
   - ahead / behind / finishing
   - leader-bashing in 4p
   - cheap neutral pickup in 4p
   - stockpile/hammer attacks after expansion

8. **They stockpile and synchronize attacks.**
   Shuming/Ajay-style agents have "hammer" plans: stockpile 50+ ships, choose high-production enemy target, launch multiple sources so fleets land together, abort if defender reinforces too much. We do greedy one-turn launches.

9. **They exploit/handle comets.**
   Strong agents model comet life and evacuation. Our comet logic is cautious and does not preserve comet ships well.

10. **Top leaderboard likely includes RL/self-play or massive replay-driven training.**
    The RL discussion describes JAX environment rewrites, entity transformers, PPO, hundreds of millions of samples, and separate 2p/4p policies or selectors. That is a different scale than our current heuristic iteration.

## What to build next

Priority order:

1. Replace our target scoring with discounted present value plus danger/race score.
2. Port the 1039 launch-safety and all-in-available offense structure.
3. Implement proper arrival ledger and timeline reserve calculation.
4. Add high-value reinforcement and doom evacuation.
5. Add 4p leader-bash and stockpile/hammer phase.
6. Use public top-replay datasets to benchmark against real strong trajectories.

The fastest practical path is not RL from scratch. It is to build a public-1000-style heuristic first, then add the 1224/Shuming-style timeline, search, and hammer systems.
