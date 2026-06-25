#!/usr/bin/env python3
"""Run Orbit Wars gauntlets against local baseline and public-kernel agents."""

from __future__ import annotations

import argparse
import contextlib
import csv
import itertools
import io
import os
from pathlib import Path
from typing import Iterable

from kaggle_environments import make


ROOT = Path(__file__).resolve().parents[1]

AGENTS = {
    "main": ROOT / "main.py",
    "nearest": ROOT / "baselines/nearest.py",
    "rush": ROOT / "baselines/rush.py",
    "static": ROOT / "baselines/static_expander.py",
    "dribbler": ROOT / "baselines/dribbler.py",
    "our_v2": ROOT / "baselines/our_v2.py",
    "our_v3": ROOT / "baselines/our_v3.py",
    "main_v5_baseline": ROOT / "baselines/main_v5_baseline.py",
    "main_v61_baseline": ROOT / "baselines/main_v61_baseline.py",
    "v4_timeline_hammer": ROOT / "baselines/v4_timeline_hammer.py",
    "public_lb1224": ROOT / "baselines/public_lb1224.py",
    "public_shuming": ROOT / "baselines/public_shuming_exp30.py",
    "public_ajay": ROOT / "baselines/public_ajay12.py",
    "public_evogen": ROOT / "baselines/public_evogen1093.py",
    "public_rahul": ROOT / "baselines/public_rahul1608.py",
    "public_lb1039": ROOT / "baselines/public_lb1039.py",
    "stable_lb1039": ROOT / "baselines/public_lb1039.py",
}

PUBLIC_POOL = [
    "public_lb1039",
    "public_lb1224",
    "public_shuming",
    "public_ajay",
    "public_evogen",
    "public_rahul",
]

WEAK_POOL = ["nearest", "rush", "static", "dribbler"]


def agent_path(name: str) -> str:
    if name in {"random", "starter"}:
        return name
    if name not in AGENTS:
        raise SystemExit(f"Unknown agent {name!r}. Known: {', '.join(sorted(AGENTS))}")
    return str(AGENTS[name])


def obs_field(obs, key, default):
    return obs.get(key, default) if isinstance(obs, dict) else getattr(obs, key, default)


def final_scores(env, players: int) -> list[int]:
    obs = env.steps[-1][0].observation
    planets = obs_field(obs, "planets", [])
    fleets = obs_field(obs, "fleets", [])
    scores = [0] * players
    for planet in planets:
        owner = int(planet[1])
        if 0 <= owner < players:
            scores[owner] += int(planet[5])
    for fleet in fleets:
        owner = int(fleet[1])
        if 0 <= owner < players:
            scores[owner] += int(fleet[6])
    return scores


def run_match(agent_names: list[str], seed: int) -> tuple[list[float], list[str], list[int]]:
    env = make("orbit_wars", configuration={"seed": seed}, debug=True)
    specs = [agent_path(name) for name in agent_names]
    noise = io.StringIO()
    with contextlib.redirect_stdout(noise), contextlib.redirect_stderr(noise):
        env.run(specs)
    rewards = [float(state.reward or 0.0) for state in env.steps[-1]]
    statuses = [state.status for state in env.steps[-1]]
    return rewards, statuses, final_scores(env, len(agent_names))


def summarize_result(
    suite: str,
    subject: str,
    opponents: tuple[str, ...],
    seat: int,
    games: int,
    seed_start: int,
) -> dict[str, object]:
    wins = ties = losses = errors = 0
    margins: list[int] = []
    rewards_seen: list[float] = []
    scores_seen: list[int] = []
    opponent_best_seen: list[int] = []

    names = list(opponents)
    names.insert(seat, subject)
    for offset in range(games):
        seed = seed_start + offset
        rewards, statuses, scores = run_match(names, seed)
        subject_reward = rewards[seat]
        rewards_seen.append(subject_reward)
        scores_seen.append(scores[seat])
        other_best = max(score for i, score in enumerate(scores) if i != seat)
        opponent_best_seen.append(other_best)
        margins.append(scores[seat] - other_best)

        if statuses[seat] != "DONE":
            errors += 1
        winners = [i for i, reward in enumerate(rewards) if reward > 0]
        if seat in winners and len(winners) == 1:
            wins += 1
        elif seat in winners:
            ties += 1
        else:
            losses += 1

    return {
        "suite": suite,
        "subject": subject,
        "opponents": "+".join(opponents),
        "seat": seat,
        "games": games,
        "seed_start": seed_start,
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "errors": errors,
        "win_rate": wins / games if games else 0.0,
        "avg_reward": sum(rewards_seen) / games if games else 0.0,
        "avg_margin": sum(margins) / games if games else 0.0,
        "avg_score": sum(scores_seen) / games if games else 0.0,
        "avg_opp_best_score": sum(opponent_best_seen) / games if games else 0.0,
    }


def four_player_groups(opponents: list[str], max_groups: int | None) -> list[tuple[str, str, str]]:
    groups = list(itertools.combinations(opponents, 3))
    if max_groups is not None:
        groups = groups[:max_groups]
    return groups


def build_jobs(
    subject: str,
    opponents: list[str],
    suites: set[str],
    max_4p_groups: int | None,
) -> list[tuple[str, tuple[str, ...], int]]:
    jobs: list[tuple[str, tuple[str, ...], int]] = []
    if "2p" in suites:
        for opponent in opponents:
            jobs.append(("2p", (opponent,), 0))
            jobs.append(("2p", (opponent,), 1))
    if "4p" in suites:
        for group in four_player_groups(opponents, max_4p_groups):
            for seat in range(4):
                jobs.append(("4p", group, seat))
    return jobs


def parse_opponents(value: str) -> list[str]:
    if value == "public":
        return PUBLIC_POOL
    if value == "weak":
        return WEAK_POOL
    if value == "all":
        return PUBLIC_POOL + WEAK_POOL
    return [part.strip() for part in value.split(",") if part.strip()]


def write_rows(rows: Iterable[dict[str, object]], output: str | None) -> None:
    rows = list(rows)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    if output:
        out_path = Path(output)
        if not out_path.is_absolute():
            out_path = ROOT / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {out_path}")
    writer = csv.DictWriter(os.sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", default="main")
    parser.add_argument(
        "--opponents",
        default="public",
        help="public, weak, all, or comma-separated agent names",
    )
    parser.add_argument("--suites", default="2p,4p", help="Comma-separated: 2p,4p")
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--max-4p-groups", type=int, default=4)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    subject = args.subject
    opponents = [name for name in parse_opponents(args.opponents) if name != subject]
    suites = {part.strip() for part in args.suites.split(",") if part.strip()}
    for name in [subject, *opponents]:
        agent_path(name)

    jobs = build_jobs(subject, opponents, suites, args.max_4p_groups)
    rows = [
        summarize_result(
            suite=suite,
            subject=subject,
            opponents=opponents_tuple,
            seat=seat,
            games=args.games,
            seed_start=args.seed_start,
        )
        for suite, opponents_tuple, seat in jobs
    ]
    write_rows(rows, args.output or None)

    if rows:
        games = sum(int(row["games"]) for row in rows)
        wins = sum(int(row["wins"]) for row in rows)
        losses = sum(int(row["losses"]) for row in rows)
        ties = sum(int(row["ties"]) for row in rows)
        errors = sum(int(row["errors"]) for row in rows)
        avg_margin = sum(float(row["avg_margin"]) * int(row["games"]) for row in rows) / games
        print(
            f"# aggregate subject={subject} wins={wins} ties={ties} "
            f"losses={losses} errors={errors} avg_margin={avg_margin:.1f}"
        )


if __name__ == "__main__":
    main()
