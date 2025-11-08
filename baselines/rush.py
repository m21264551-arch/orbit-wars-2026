import math

from kaggle_environments.envs.orbit_wars.orbit_wars import CENTER, ROTATION_RADIUS_LIMIT, Planet


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def crosses_sun(a, b):
    px, py = CENTER, CENTER
    vx, vy = a
    wx, wy = b
    lx = wx - vx
    ly = wy - vy
    l2 = lx * lx + ly * ly
    if l2 <= 1e-12:
        return dist((px, py), a) < 10.4
    t = max(0.0, min(1.0, ((px - vx) * lx + (py - vy) * ly) / l2))
    return dist((px, py), (vx + t * lx, vy + t * ly)) < 10.4


def agent(obs):
    player = obs.get("player", 0)
    step = obs.get("step", 0)
    planets = [Planet(*p) for p in obs.get("planets", [])]
    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    moves = []

    for mine in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        spare = mine.ships - (1 if step < 80 else max(3, p.production if (p := mine) else 1))
        if spare <= 0:
            continue
        best = None
        for target in targets:
            d = dist((mine.x, mine.y), (target.x, target.y))
            if crosses_sun((mine.x, mine.y), (target.x, target.y)):
                continue
            need = target.ships + 1
            if target.owner != -1:
                need += max(0, int(d / 4.0)) * target.production
            send = min(spare, max(1, need))
            if send > spare:
                continue
            orbital = dist((target.x, target.y), (CENTER, CENTER))
            static_bonus = 1.08 if orbital + target.radius >= ROTATION_RADIUS_LIMIT else 1.0
            score = static_bonus * (target.production * 45.0 - target.ships) / (need + d * 0.45)
            if best is None or score > best[0]:
                best = (score, target, send)
        if best is None:
            continue
        _, target, send = best
        moves.append([mine.id, math.atan2(target.y - mine.y, target.x - mine.x), int(send)])
    return moves
