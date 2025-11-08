import math

from kaggle_environments.envs.orbit_wars.orbit_wars import Planet


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def agent(obs):
    player = obs.get("player", 0)
    planets = [Planet(*p) for p in obs.get("planets", [])]
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    moves = []

    for mine in my_planets:
        if mine.ships < 12:
            continue
        ranked = sorted(
            targets,
            key=lambda t: (-(t.production * 12 - t.ships), dist((mine.x, mine.y), (t.x, t.y))),
        )
        for target in ranked[:2]:
            send = min(10, max(2, mine.ships // 3))
            if send < mine.ships:
                moves.append([mine.id, math.atan2(target.y - mine.y, target.x - mine.x), int(send)])
                break
    return moves
