#!/usr/bin/env python3
"""Run a single Orbit Wars match and emit a JSON line summarizing the result.

The variant agent (main.py with env-var overrides applied) plays from
``--variant-seat``; opponent fills the other seat. JSON line printed to stdout:
{"status": "win"|"tie"|"loss", "margin": int, "scores": [...], "rewards": [...]}.

Designed to be spawned per-variant by tune.py so env-var-read-at-import-time
parameter sweeps actually work.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from pathlib import Path

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]


def obs_field(obs, key, default):
    return obs.get(key, default) if isinstance(obs, dict) else getattr(obs, key, default)


def final_scores(env, players: int) -> list[int]:
    obs = env.steps[-1][0].observation
    planets = obs_field(obs, "planets", [])
    fleets = obs_field(obs, "fleets", [])
    scores = [0] * players
    for p in planets:
        owner = int(p[1])
        if 0 <= owner < players:
            scores[owner] += int(p[5])
    for f in fleets:
        owner = int(f[1])
        if 0 <= owner < players:
            scores[owner] += int(f[6])
    return scores


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--opponent", required=True)
    ap.add_argument("--variant-seat", type=int, default=0)
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args()

    variant = ROOT / args.variant
    opponent = ROOT / args.opponent
    if args.variant_seat == 0:
        specs = [str(variant), str(opponent)]
    else:
        specs = [str(opponent), str(variant)]

    env = make("orbit_wars", configuration={"seed": args.seed}, debug=True)
    noise = io.StringIO()
    with contextlib.redirect_stdout(noise), contextlib.redirect_stderr(noise):
        env.run(specs)
    rewards = [float(s.reward or 0.0) for s in env.steps[-1]]
    scores = final_scores(env, len(specs))
    variant_reward = rewards[args.variant_seat]
    other_best = max(s for i, s in enumerate(scores) if i != args.variant_seat)
    margin = scores[args.variant_seat] - other_best
    if variant_reward > 0:
        winners = [i for i, r in enumerate(rewards) if r > 0]
        status = "win" if len(winners) == 1 else "tie"
    else:
        status = "loss"

    print(json.dumps({"status": status, "margin": margin, "scores": scores,
                      "rewards": rewards, "variant_seat": args.variant_seat,
                      "seed": args.seed}))


if __name__ == "__main__":
    main()
