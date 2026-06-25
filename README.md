# Orbit Wars 2026

This repo contains my Orbit Wars competition agent, benchmarking tools, baseline agents, and tuning notes.

Orbit Wars is a turn-based strategy game where players launch fleets between moving planets while a central sun and comet paths create collision risk.

## What is included

- `main.py` as the current competition agent
- `baselines/` with earlier agents and public-agent references used for comparison
- `tools/benchmark.py` and `tools/match_runner.py` for local evaluation
- `tools/tune.py` for parameter sweeps
- `tools/analyze_replays.py` for replay diagnostics
- `notes/` with validation logs, ablations, and tuning outputs

## Agent focus

The current work is practical competition engineering. It compares variants across many seeds, watches failure modes in replays, and promotes changes only when they improve against the local benchmark set.

The repo includes several public-agent baselines because they were useful reference opponents during tuning.

## Run a benchmark

```bash
python tools/benchmark.py --suite public --games 3 --seed-start 10000
```

Run a match directly:

```bash
python tools/match_runner.py --agents main.py baselines/nearest.py
```

## Game summary

Players control planets and launch fleets. Planets may orbit the sun, fleets move in straight lines, and collisions with the sun or planets matter. Final score is based on ships on owned planets and ships in flight.

The observation includes planets, fleets, player id, comet data, and remaining overage time. Actions are lists of launches in the form:

```python
[[from_planet_id, direction_angle, num_ships]]
```

## Notes

This is a competition workspace, not a polished game package. The value is in the agent code, benchmark tooling, and experiment history.
