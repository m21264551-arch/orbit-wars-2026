import math

from kaggle_environments.envs.orbit_wars.orbit_wars import CENTER, ROTATION_RADIUS_LIMIT, Planet


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def is_static(p):
    return dist((p.x, p.y), (CENTER, CENTER)) + p.radius >= ROTATION_RADIUS_LIMIT


def agent(obs):
    player = obs.get("player", 0)
    planets = [Planet(*p) for p in obs.get("planets", [])]
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    moves = []

    for mine in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        spare = mine.ships - max(1, mine.production)
        if spare <= 0:
            continue
        best = None
        for target in targets:
            d = dist((mine.x, mine.y), (target.x, target.y))
            need = target.ships + 1
            if target.owner != -1:
                need += int(d / 3.5) * target.production
            if need > spare:
                continue
            score = (target.production * (2.2 if is_static(target) else 1.0)) / (need + d * 0.2)
            if best is None or score > best[0]:
                best = (score, target, need)
        if best:
            _, target, send = best
            moves.append([mine.id, math.atan2(target.y - mine.y, target.x - mine.x), int(send)])
    return moves
