#!/usr/bin/env python3
import argparse
import glob
import json
import os
from collections import defaultdict


CHECKPOINTS = [0, 1, 3, 5, 10, 20, 30, 50, 75, 100, 150, 250, 499]


def load_replays(patterns):
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    return sorted(set(files))


def obs_at(data, turn):
    return data["steps"][turn][0]["observation"]


def actions_at(data, turn):
    return [state.get("action") or [] for state in data["steps"][turn]]


def team_names(data):
    return data.get("info", {}).get("TeamNames") or [
        agent.get("Name", f"agent_{i}")
        for i, agent in enumerate(data.get("info", {}).get("Agents", []))
    ]


def find_team_index(data, team):
    names = team_names(data)
    if team is None:
        return 0
    needle = team.lower()
    for i, name in enumerate(names):
        if needle in name.lower():
            return i
    return 0


def metrics(obs, players):
    planets = obs.get("planets", [])
    fleets = obs.get("fleets", [])
    rows = []
    for pid in range(players):
        owned = [p for p in planets if p[1] == pid]
        owned_fleets = [f for f in fleets if f[1] == pid]
        planet_ships = sum(int(p[5]) for p in owned)
        fleet_ships = sum(int(f[6]) for f in owned_fleets)
        rows.append(
            {
                "planets": len(owned),
                "production": sum(int(p[6]) for p in owned),
                "score": planet_ships + fleet_ships,
                "planet_ships": planet_ships,
                "fleet_ships": fleet_ships,
                "fleets": len(owned_fleets),
            }
        )
    return rows


def first_action_turn(data, player):
    for turn in range(len(data["steps"])):
        if actions_at(data, turn)[player]:
            return turn
    return None


def first_capture_turns(data, players):
    first = [None] * players
    previous = None
    for turn in range(len(data["steps"])):
        owners = {p[0]: p[1] for p in obs_at(data, turn).get("planets", [])}
        if previous is None:
            previous = owners
            continue
        for pid, owner in owners.items():
            old = previous.get(pid, -1)
            if owner >= 0 and owner != old and first[owner] is None:
                first[owner] = turn
        previous = owners
    return first


def capture_events(data):
    events = []
    previous = None
    for turn in range(len(data["steps"])):
        planets = {p[0]: p for p in obs_at(data, turn).get("planets", [])}
        owners = {pid: p[1] for pid, p in planets.items()}
        if previous is None:
            previous = owners
            continue
        for pid, owner in owners.items():
            old = previous.get(pid, -1)
            if owner != old:
                p = planets[pid]
                events.append(
                    {
                        "turn": turn,
                        "planet": pid,
                        "from": old,
                        "to": owner,
                        "ships": int(p[5]),
                        "production": int(p[6]),
                    }
                )
        previous = owners
    return events


def classify_loss(data, player):
    rewards = data.get("rewards") or []
    if player >= len(rewards) or rewards[player] > 0:
        return "not_loss"
    winner = max(range(len(rewards)), key=lambda i: rewards[i])
    final_turn = len(data["steps"]) - 1
    t50 = min(50, final_turn)
    t75 = min(75, final_turn)
    m50 = metrics(obs_at(data, t50), len(rewards))
    m75 = metrics(obs_at(data, t75), len(rewards))
    ours50, win50 = m50[player], m50[winner]
    ours75, win75 = m75[player], m75[winner]
    if win50["production"] >= ours50["production"] + 10:
        return "out-expanded-by-t50"
    if win75["production"] >= ours75["production"] + 12:
        return "out-expanded-by-t75"
    if win75["fleet_ships"] >= ours75["fleet_ships"] + 180:
        return "fleet-mass-deficit"
    return "combat-or-endgame"


def summarize_file(path, team, opening_turns):
    with open(path) as f:
        data = json.load(f)
    names = team_names(data)
    players = len(names)
    player = find_team_index(data, team)
    rewards = data.get("rewards") or [None] * players
    first_caps = first_capture_turns(data, players)
    first_actions = [first_action_turn(data, i) for i in range(players)]
    winner = [i for i, reward in enumerate(rewards) if reward and reward > 0]
    winner_text = ",".join(names[i] for i in winner) if winner else "none"

    print(f"\n=== {os.path.basename(path)} ===")
    print(f"episode: {data.get('info', {}).get('EpisodeId')}  players: {players}  turns: {len(data['steps']) - 1}")
    print(f"teams: {names}")
    print(f"tracked: p{player} {names[player]}  rewards: {rewards}  winner: {winner_text}")
    print(f"classification: {classify_loss(data, player)}")
    print("first actions:", ", ".join(f"p{i}={turn}" for i, turn in enumerate(first_actions)))
    print("first captures:", ", ".join(f"p{i}={turn}" for i, turn in enumerate(first_caps)))

    print("\nturn,p,planets,prod,score,planet_ships,fleet_ships,fleets")
    for turn in CHECKPOINTS:
        if turn >= len(data["steps"]):
            continue
        rows = metrics(obs_at(data, turn), players)
        for i, row in enumerate(rows):
            if i == player or rewards[i] and rewards[i] > 0:
                print(
                    f"{turn},{i},{row['planets']},{row['production']},{row['score']},"
                    f"{row['planet_ships']},{row['fleet_ships']},{row['fleets']}"
                )

    print(f"\nopening actions, first {opening_turns} turns")
    for turn in range(min(opening_turns, len(data["steps"]))):
        acts = actions_at(data, turn)
        if not any(acts):
            continue
        parts = []
        for i, action in enumerate(acts):
            if action:
                parts.append(f"p{i}:{action[:4]}")
        print(f"t{turn}: " + "  ".join(parts))

    events_by_owner = defaultdict(list)
    for event in capture_events(data):
        if event["to"] >= 0:
            events_by_owner[event["to"]].append(event)
    print("\nearly captures")
    for i in range(players):
        events = events_by_owner[i][:8]
        if not events:
            continue
        brief = [
            f"t{e['turn']} planet {e['planet']} prod {e['production']} ships {e['ships']}"
            for e in events
        ]
        print(f"p{i}: " + "; ".join(brief))


def main():
    parser = argparse.ArgumentParser(description="Summarize Orbit Wars replay economy and opening tempo.")
    parser.add_argument("patterns", nargs="*", default=["replays/*.json"])
    parser.add_argument("--team", default="JosephMontana")
    parser.add_argument("--opening-turns", type=int, default=20)
    args = parser.parse_args()

    files = load_replays(args.patterns)
    if not files:
        raise SystemExit("No replay files matched.")
    for path in files:
        summarize_file(path, args.team, args.opening_turns)


if __name__ == "__main__":
    main()
