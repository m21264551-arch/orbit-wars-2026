#!/usr/bin/env python3
"""Self-play parameter tuner for Orbit Wars.

Pits a parameter-variant of main.py against the un-tuned main.py (or
public_shuming) across many seeds with seat rotation. Reports wins/ties/losses
and avg margin so we can pick the variant that dominates the baseline.

Each variant is specified as ``KEY=VALUE`` pairs (env vars consumed by main.py
via ``os.environ.get("TUNE_...")``). main.py reads env vars at import time, so
each variant runs in a fresh subprocess via `match_runner.py`.

Usage:
    python tools/tune.py \
        --multi TUNE_HAMMER_OVERKILL=1.20,1.30,1.40 --games 3

    python tools/tune.py \
        --multi TUNE_HAMMER_OVERKILL=1.20,1.30 \
        --multi TUNE_VALUE_WEIGHT_2P=4.0,5.5 --games 3
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "match_runner.py"


def parse_multi(specs: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for s in specs:
        if "=" not in s:
            raise SystemExit(f"--multi expected KEY=v1,v2,... got {s!r}")
        key, vals = s.split("=", 1)
        out[key.strip()] = [v.strip() for v in vals.split(",") if v.strip()]
    return out


def run_variant(overrides: dict[str, str], opponent: str, games: int,
                seed_start: int) -> dict:
    """Spawn match_runner.py per (variant_seat, seed) pair in subprocess."""
    wins = ties = losses = 0
    margins: list[float] = []
    n = 0

    for offset in range(games):
        seed = seed_start + offset
        for variant_seat in (0, 1):
            env = os.environ.copy()
            for k, v in overrides.items():
                env[k] = v
            cmd = [
                sys.executable, str(RUNNER),
                "--variant-seat", str(variant_seat),
                "--variant", "main.py",
                "--opponent", opponent,
                "--seed", str(seed),
            ]
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180)
            if proc.returncode != 0:
                print(f"runner failed: rc={proc.returncode}\n{proc.stderr}", file=sys.stderr)
                continue
            try:
                res = json.loads(proc.stdout.strip().splitlines()[-1])
            except (json.JSONDecodeError, IndexError) as exc:
                print(f"parse failed: {exc}\nstdout={proc.stdout}", file=sys.stderr)
                continue
            n += 1
            margins.append(res["margin"])
            if res["status"] == "win":
                wins += 1
            elif res["status"] == "tie":
                ties += 1
            else:
                losses += 1

    return {
        "games": n,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_rate": wins / n if n else 0.0,
        "avg_margin": sum(margins) / n if n else 0.0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--multi", action="append", default=[])
    p.add_argument("--opponent", default="baselines/public_shuming_exp30.py")
    p.add_argument("--games", type=int, default=3)
    p.add_argument("--seed-start", type=int, default=20000)
    p.add_argument("--output", default="")
    args = p.parse_args()

    multi = parse_multi(args.multi) if args.multi else {}
    if not multi:
        result = run_variant({}, args.opponent, args.games, args.seed_start)
        print(json.dumps({"overrides": {}, **result}, indent=2))
        return

    keys = list(multi.keys())
    combos = list(itertools.product(*[multi[k] for k in keys]))
    results: list[dict] = []
    for combo in combos:
        overrides = dict(zip(keys, combo))
        print(f"\n=== variant: {overrides} ===", file=sys.stderr)
        result = run_variant(overrides, args.opponent, args.games, args.seed_start)
        result["overrides"] = overrides
        results.append(result)
        print(
            f"  wins={result['wins']} ties={result['ties']} losses={result['losses']}"
            f"  win_rate={result['win_rate']:.2f}  avg_margin={result['avg_margin']:.0f}",
            file=sys.stderr,
        )

    results.sort(key=lambda r: (r["wins"] + 0.5 * r["ties"], r["avg_margin"]), reverse=True)
    print("\n# Ranked variants (best first):")
    for r in results:
        print(
            f"  {r['overrides']}  →  wins={r['wins']}/{r['games']} "
            f"ties={r['ties']} losses={r['losses']}  avg_margin={r['avg_margin']:.0f}"
        )

    if args.output:
        out_path = Path(args.output)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
