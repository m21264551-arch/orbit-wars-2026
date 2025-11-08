#!/usr/bin/env python3
import argparse
import contextlib
import io
import os

from kaggle_environments import make


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(ROOT, "main.py")
NEAREST = os.path.join(ROOT, "baselines", "nearest.py")
RUSH = os.path.join(ROOT, "baselines", "rush.py")
STATIC = os.path.join(ROOT, "baselines", "static_expander.py")
DRIBBLER = os.path.join(ROOT, "baselines", "dribbler.py")
OUR_V3 = os.path.join(ROOT, "baselines", "our_v3.py")
PUB_LB1039 = os.path.join(ROOT, "baselines", "public_lb1039.py")
PUB_LB1224 = os.path.join(ROOT, "baselines", "public_lb1224.py")
PUB_SHUMING = os.path.join(ROOT, "baselines", "public_shuming_exp30.py")
PUB_AJAY = os.path.join(ROOT, "baselines", "public_ajay12.py")


def final_scores(env, players):
    obs = env.steps[-1][0].observation
    planets = obs["planets"] if isinstance(obs, dict) else obs.planets
    fleets = obs["fleets"] if isinstance(obs, dict) else obs.fleets
    scores = [0] * players
    for planet in planets:
        owner = planet[1]
        if 0 <= owner < players:
            scores[owner] += int(planet[5])
    for fleet in fleets:
        owner = fleet[1]
        if 0 <= owner < players:
            scores[owner] += int(fleet[6])
    return scores


def run_match(agents, seed):
    env = make("orbit_wars", configuration={"seed": seed}, debug=True)
    noise = io.StringIO()
    with contextlib.redirect_stdout(noise), contextlib.redirect_stderr(noise):
        env.run(agents)
    rewards = [state.reward for state in env.steps[-1]]
    statuses = [state.status for state in env.steps[-1]]
    return rewards, statuses, final_scores(env, len(agents))


def match_specs(suite):
    two_player = [
        ("2p_random_p0", [MAIN, "random"], 0),
        ("2p_random_p1", ["random", MAIN], 1),
        ("2p_starter_p0", [MAIN, "starter"], 0),
        ("2p_starter_p1", ["starter", MAIN], 1),
        ("2p_nearest_p0", [MAIN, NEAREST], 0),
        ("2p_nearest_p1", [NEAREST, MAIN], 1),
    ]
    four_player = [
        ("4p_mixed_p0", [MAIN, "starter", "random", NEAREST], 0),
        ("4p_mixed_p1", ["starter", MAIN, "random", NEAREST], 1),
        ("4p_mixed_p2", ["starter", "random", MAIN, NEAREST], 2),
        ("4p_mixed_p3", ["starter", "random", NEAREST, MAIN], 3),
    ]
    adversarial = [
        ("2p_rush_p0", [MAIN, RUSH], 0),
        ("2p_rush_p1", [RUSH, MAIN], 1),
        ("2p_static_p0", [MAIN, STATIC], 0),
        ("2p_static_p1", [STATIC, MAIN], 1),
        ("2p_dribbler_p0", [MAIN, DRIBBLER], 0),
        ("2p_dribbler_p1", [DRIBBLER, MAIN], 1),
        ("4p_adv_p0", [MAIN, RUSH, STATIC, DRIBBLER], 0),
        ("4p_adv_p1", [RUSH, MAIN, STATIC, DRIBBLER], 1),
        ("4p_adv_p2", [RUSH, STATIC, MAIN, DRIBBLER], 2),
        ("4p_adv_p3", [RUSH, STATIC, DRIBBLER, MAIN], 3),
    ]
    if suite == "2p":
        return two_player
    if suite == "4p":
        return four_player
    if suite == "quick":
        return [
            ("2p_starter_p0", [MAIN, "starter"], 0),
            ("2p_starter_p1", ["starter", MAIN], 1),
            ("4p_mixed_p0", [MAIN, "starter", "random", NEAREST], 0),
        ]
    if suite == "adv":
        return adversarial
    if suite == "public":
        return [
            ("2p_v3_p0", [MAIN, OUR_V3], 0),
            ("2p_v3_p1", [OUR_V3, MAIN], 1),
            ("2p_lb1039_p0", [MAIN, PUB_LB1039], 0),
            ("2p_lb1039_p1", [PUB_LB1039, MAIN], 1),
            ("2p_lb1224_p0", [MAIN, PUB_LB1224], 0),
            ("2p_lb1224_p1", [PUB_LB1224, MAIN], 1),
            ("2p_shuming_p0", [MAIN, PUB_SHUMING], 0),
            ("2p_shuming_p1", [PUB_SHUMING, MAIN], 1),
            ("2p_ajay_p0", [MAIN, PUB_AJAY], 0),
            ("2p_ajay_p1", [PUB_AJAY, MAIN], 1),
            ("4p_pub_p0", [MAIN, PUB_LB1039, PUB_LB1224, PUB_SHUMING], 0),
            ("4p_pub_p1", [PUB_LB1039, MAIN, PUB_LB1224, PUB_SHUMING], 1),
            ("4p_pub_p2", [PUB_LB1039, PUB_LB1224, MAIN, PUB_SHUMING], 2),
            ("4p_pub_p3", [PUB_LB1039, PUB_LB1224, PUB_SHUMING, MAIN], 3),
        ]
    return two_player + four_player + adversarial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=1)
    parser.add_argument("--suite", choices=["all", "2p", "4p", "quick", "adv", "public"], default="quick")
    args = parser.parse_args()

    aggregate = {}
    for name, agents, our_index in match_specs(args.suite):
        wins = losses = errors = ties = 0
        margins = []
        for offset in range(args.games):
            seed = args.seed_start + offset
            rewards, statuses, scores = run_match(agents, seed)
            if statuses[our_index] != "DONE":
                errors += 1
            reward = rewards[our_index]
            if reward > 0:
                winners = [i for i, value in enumerate(rewards) if value > 0]
                if len(winners) > 1:
                    ties += 1
                else:
                    wins += 1
            else:
                losses += 1
            other_best = max(score for i, score in enumerate(scores) if i != our_index)
            margins.append(scores[our_index] - other_best)
        aggregate[name] = (wins, ties, losses, errors, sum(margins) / len(margins))

    print("match,wins,ties,losses,errors,avg_margin")
    for name, values in aggregate.items():
        print(f"{name},{values[0]},{values[1]},{values[2]},{values[3]},{values[4]:.1f}")


if __name__ == "__main__":
    main()
