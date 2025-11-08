import math


BOARD_SIZE = 100.0
CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0
MAX_TURNS = 500

ID, OWNER, X, Y, RADIUS, SHIPS, PROD = range(7)
F_ID, F_OWNER, F_X, F_Y, F_ANGLE, F_FROM, F_SHIPS = range(7)


def get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fleet_speed(ships):
    ships = max(1, int(ships))
    speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000.0)) ** 1.5
    return min(MAX_SPEED, speed)


def point_segment_distance(p, v, w):
    lx = w[0] - v[0]
    ly = w[1] - v[1]
    l2 = lx * lx + ly * ly
    if l2 <= 1e-12:
        return dist(p, v)
    t = ((p[0] - v[0]) * lx + (p[1] - v[1]) * ly) / l2
    t = max(0.0, min(1.0, t))
    proj = (v[0] + t * lx, v[1] + t * ly)
    return dist(p, proj)


def swept_pair_hit(a, b, p0, p1, radius):
    d0x = a[0] - p0[0]
    d0y = a[1] - p0[1]
    dvx = (b[0] - a[0]) - (p1[0] - p0[0])
    dvy = (b[1] - a[1]) - (p1[1] - p0[1])
    qa = dvx * dvx + dvy * dvy
    qb = 2.0 * (d0x * dvx + d0y * dvy)
    qc = d0x * d0x + d0y * d0y - radius * radius
    if qa < 1e-12:
        return qc <= 0.0
    disc = qb * qb - 4.0 * qa * qc
    if disc < 0.0:
        return False
    root = math.sqrt(disc)
    t1 = (-qb - root) / (2.0 * qa)
    t2 = (-qb + root) / (2.0 * qa)
    return t2 >= 0.0 and t1 <= 1.0


def line_crosses_sun(a, b, margin=0.25):
    return point_segment_distance((CENTER, CENTER), a, b) < SUN_RADIUS + margin


def is_rotating(planet, initial):
    base = initial.get(planet[ID], planet)
    orbital = math.hypot(base[X] - CENTER, base[Y] - CENTER)
    return orbital + planet[RADIUS] < ROTATION_RADIUS_LIMIT


def comet_lookup(comets):
    lookup = {}
    for group in comets:
        ids = group.get("planet_ids", [])
        paths = group.get("paths", [])
        idx = int(group.get("path_index", -1))
        for i, pid in enumerate(ids):
            if i < len(paths):
                lookup[pid] = (paths[i], idx)
    return lookup


def planet_position(planet, lead, step, angular_velocity, initial, comets_by_id):
    pid = planet[ID]
    if pid in comets_by_id:
        path, idx = comets_by_id[pid]
        if not path:
            return (planet[X], planet[Y])
        future_idx = idx + int(round(max(0.0, lead)))
        future_idx = max(0, min(len(path) - 1, future_idx))
        return (path[future_idx][0], path[future_idx][1])

    base = initial.get(pid, planet)
    orbital = math.hypot(base[X] - CENTER, base[Y] - CENTER)
    if orbital + planet[RADIUS] >= ROTATION_RADIUS_LIMIT:
        return (planet[X], planet[Y])

    angle0 = math.atan2(base[Y] - CENTER, base[X] - CENTER)
    rotation_tick = max(0.0, float(step) + max(0.0, lead) - 1.0)
    angle = angle0 + angular_velocity * rotation_tick
    return (CENTER + orbital * math.cos(angle), CENTER + orbital * math.sin(angle))


def alive_comet_time(planet, comets_by_id):
    if planet[ID] not in comets_by_id:
        return 10 ** 9
    path, idx = comets_by_id[planet[ID]]
    return max(0, len(path) - idx - 1)


def aim_solution(source, target, ships, step, angular_velocity, initial, comets_by_id):
    speed = fleet_speed(ships)
    start = (source[X], source[Y])
    lead = max(1.0, dist(start, (target[X], target[Y])) / speed)
    for _ in range(5):
        future = planet_position(target, lead, step, angular_velocity, initial, comets_by_id)
        lead = max(1.0, dist(start, future) / speed)

    center = planet_position(target, lead, step, angular_velocity, initial, comets_by_id)
    options = [center]
    r = max(0.2, target[RADIUS] * 0.82)
    for k in range(12):
        theta = 2.0 * math.pi * k / 12.0
        options.append((center[0] + r * math.cos(theta), center[1] + r * math.sin(theta)))

    best = None
    best_cost = float("inf")
    direct_angle = math.atan2(center[1] - start[1], center[0] - start[0])
    for point in options:
        if line_crosses_sun(start, point):
            continue
        angle = math.atan2(point[1] - start[1], point[0] - start[0])
        eta = max(1.0, dist(start, point) / speed)
        cost = abs(math.atan2(math.sin(angle - direct_angle), math.cos(angle - direct_angle))) + 0.002 * eta
        if cost < best_cost:
            best = (angle, eta, point)
            best_cost = cost
    return best


def first_hit(owner, start, angle, ships, planets, step, angular_velocity, initial, comets_by_id, horizon=150):
    speed = fleet_speed(ships)
    pos = start
    for tick in range(horizon):
        new_pos = (pos[0] + math.cos(angle) * speed, pos[1] + math.sin(angle) * speed)
        for planet in planets:
            p0 = planet_position(planet, tick, step, angular_velocity, initial, comets_by_id)
            p1 = planet_position(planet, tick + 1, step, angular_velocity, initial, comets_by_id)
            if swept_pair_hit(pos, new_pos, p0, p1, planet[RADIUS]):
                return planet[ID], tick + 1
        if not (0.0 <= new_pos[0] <= BOARD_SIZE and 0.0 <= new_pos[1] <= BOARD_SIZE):
            return None, tick + 1
        if line_crosses_sun(pos, new_pos, margin=0.0):
            return None, tick + 1
        pos = new_pos
    return None, horizon


def incoming_map(fleets, planets, step, angular_velocity, initial, comets_by_id):
    incoming = {}
    for fleet in fleets:
        start = (fleet[F_X], fleet[F_Y])
        pid, eta = first_hit(
            fleet[F_OWNER],
            start,
            fleet[F_ANGLE],
            fleet[F_SHIPS],
            planets,
            step,
            angular_velocity,
            initial,
            comets_by_id,
            horizon=120,
        )
        if pid is None:
            continue
        incoming.setdefault(pid, []).append((fleet[F_OWNER], int(fleet[F_SHIPS]), eta))
    return incoming


def current_scores(planets, fleets, players=4):
    scores = [0] * players
    for planet in planets:
        owner = planet[OWNER]
        if 0 <= owner < players:
            scores[owner] += int(planet[SHIPS])
    for fleet in fleets:
        owner = fleet[F_OWNER]
        if 0 <= owner < players:
            scores[owner] += int(fleet[F_SHIPS])
    return scores


def ships_committed(incoming, pid, owner, eta_limit):
    return sum(ships for who, ships, eta in incoming.get(pid, []) if who == owner and eta <= eta_limit)


def enemy_committed(incoming, pid, player, eta_limit):
    return sum(ships for who, ships, eta in incoming.get(pid, []) if who != player and eta <= eta_limit)


def capture_need(target, player, eta, incoming):
    eta_limit = eta + 6
    mine = ships_committed(incoming, target[ID], player, eta_limit)
    enemies = enemy_committed(incoming, target[ID], player, eta_limit)
    need = int(target[SHIPS]) + 1

    if target[OWNER] != -1 and target[OWNER] != player:
        need += int(target[PROD] * max(0, eta - 1))
        need += ships_committed(incoming, target[ID], target[OWNER], eta_limit)
    elif target[OWNER] == -1 and enemies > target[SHIPS]:
        need += max(0, enemies - int(target[SHIPS]))

    need -= mine
    return max(0, need)


def reserve_for(planet, player, incoming):
    base = max(1, min(int(planet[SHIPS]), 2 + int(planet[PROD]) * 2))
    threats = [(ships, eta) for who, ships, eta in incoming.get(planet[ID], []) if who != player]
    if not threats:
        return base

    reserve = base
    for ships, eta in threats:
        friendly = ships_committed(incoming, planet[ID], player, eta)
        produced = int(planet[PROD] * max(0, eta - 1))
        need = ships + 3 - friendly - produced
        reserve = max(reserve, need)
    return max(0, min(int(planet[SHIPS]), reserve))


def target_value(source, target, player, ships, eta, step, incoming, comets_by_id, initial, player_count):
    remaining = max(1, MAX_TURNS - step)
    if eta >= remaining - 2:
        return -1e9
    if target[ID] in comets_by_id and eta + 4 >= alive_comet_time(target, comets_by_id):
        return -1e9

    production_window = max(0.0, remaining - eta)
    swing = target[PROD] * production_window
    owner = target[OWNER]
    if owner == -1:
        swing *= 1.25
    elif owner != player:
        swing *= 2.15
    else:
        return -1e9

    if target[ID] in comets_by_id:
        swing *= 0.45

    distance = dist((source[X], source[Y]), (target[X], target[Y]))
    cost = max(1.0, ships) + 0.55 * eta + 0.025 * distance
    score = swing / cost
    score += 0.30 * target[PROD]
    score -= 0.012 * max(0, target[SHIPS])

    if player_count >= 4 and owner != -1 and target[ID] not in comets_by_id:
        if is_rotating(target, initial):
            score *= 0.96
        else:
            score *= 1.08

    if owner != -1 and step < 100:
        score *= 0.45
    if owner == -1 and step < 130:
        score *= 1.20
    if enemy_committed(incoming, target[ID], player, eta + 4) > target[SHIPS] and owner == -1:
        score *= 0.72
    return score


def legal_verified_move(source, target, ships, planets, step, angular_velocity, initial, comets_by_id):
    aim = aim_solution(source, target, ships, step, angular_velocity, initial, comets_by_id)
    if aim is None:
        return None
    angle, eta, _ = aim
    start = (
        source[X] + math.cos(angle) * (source[RADIUS] + 0.1),
        source[Y] + math.sin(angle) * (source[RADIUS] + 0.1),
    )
    pid, hit_eta = first_hit(
        source[OWNER],
        start,
        angle,
        ships,
        planets,
        step,
        angular_velocity,
        initial,
        comets_by_id,
        horizon=min(180, int(max(20, eta + 20))),
    )
    if pid != target[ID]:
        return None
    return [source[ID], angle, int(ships)], hit_eta


def opening_leave(source, step):
    if step < 25:
        return 1
    if step < 55:
        return max(1, min(int(source[PROD]), 4))
    return max(2, min(int(source[PROD]) + 1, 6))


def opening_target_score(source, target, ships, eta, step, initial, comets_by_id, player_count):
    if target[ID] in comets_by_id:
        life = alive_comet_time(target, comets_by_id)
        if eta + 8 >= life:
            return -1e9

    production = int(target[PROD])
    distance = dist((source[X], source[Y]), (target[X], target[Y]))
    payback_turns = max(1.0, min(150.0, MAX_TURNS - step - eta))
    score = production * payback_turns / (max(1, ships) + 0.35 * eta + 0.04 * distance)

    if production <= 1:
        score *= 0.25 if step < 65 else 0.55
    elif production == 2:
        score *= 0.75
    elif production >= 4:
        score *= 1.38

    if target[ID] not in comets_by_id and not is_rotating(target, initial):
        score *= 1.08 if player_count >= 4 else 1.03

    if step < 25 and eta <= 18:
        score *= 1.14
    if target[SHIPS] <= 10 and production >= 3:
        score *= 1.20
    return score


def opening_moves(
    player,
    step,
    planets,
    my_planets,
    angular_velocity,
    initial,
    comets_by_id,
    incoming,
    player_count,
):
    if step > 90:
        return [], {}

    moves = []
    spent = {}
    neutrals = [p for p in planets if p[OWNER] == -1]
    if not neutrals:
        return moves, spent

    max_moves = 2 if step < 35 else 4
    sources = sorted(my_planets, key=lambda p: (int(p[SHIPS]), int(p[PROD])), reverse=True)
    for source in sources:
        sid = source[ID]
        spare = int(source[SHIPS]) - spent.get(sid, 0) - opening_leave(source, step)
        if spare <= 0:
            continue

        best = None
        for target in neutrals:
            if target[ID] in comets_by_id and alive_comet_time(target, comets_by_id) < 12:
                continue

            committed = ships_committed(incoming, target[ID], player, 120)
            base_need = max(0, int(target[SHIPS]) + 1 - committed)
            if base_need <= 0 or base_need > spare:
                continue

            send_options = {
                base_need,
                min(spare, base_need + int(target[PROD]) * 2),
                min(spare, int(base_need * 1.35) + 3),
            }

            for send in sorted(send_options):
                if send <= 0 or send > spare:
                    continue
                candidate = legal_verified_move(
                    source,
                    target,
                    send,
                    planets,
                    step,
                    angular_velocity,
                    initial,
                    comets_by_id,
                )
                if candidate is None:
                    continue
                action, hit_eta = candidate
                need = capture_need(target, player, hit_eta, incoming)
                if need <= 0:
                    continue
                if send < need:
                    send = need
                    if send > spare:
                        continue
                    candidate = legal_verified_move(
                        source,
                        target,
                        send,
                        planets,
                        step,
                        angular_velocity,
                        initial,
                        comets_by_id,
                    )
                    if candidate is None:
                        continue
                    action, hit_eta = candidate

                score = opening_target_score(
                    source,
                    target,
                    send,
                    hit_eta,
                    step,
                    initial,
                    comets_by_id,
                    player_count,
                )
                if best is None or score > best[0]:
                    best = (score, action, target[ID], int(send), hit_eta, int(target[PROD]))

        if best is None:
            continue

        score, action, target_id, send, hit_eta, production = best
        threshold = 2.15 if step < 35 else 1.35
        if production <= 1 and step < 50:
            threshold *= 1.75
        if score < threshold:
            continue

        moves.append(action)
        spent[sid] = spent.get(sid, 0) + send
        incoming.setdefault(target_id, []).append((player, send, hit_eta))
        if len(moves) >= max_moves:
            break

    return moves, spent


def choose_send_amount(
    source,
    target,
    player,
    available,
    step,
    angular_velocity,
    initial,
    comets_by_id,
    incoming,
    player_count,
):
    if available <= 0:
        return None
    probes = set()
    for raw in (
        int(target[SHIPS]) + 1,
        int(target[SHIPS]) + int(target[PROD]) + 2,
        int(available * 0.45),
        int(available * 0.65),
        int(available),
    ):
        if raw > 0:
            probes.add(min(int(available), max(1, raw)))

    best = None
    best_score = -1e9
    for ships in sorted(probes):
        aim = aim_solution(source, target, ships, step, angular_velocity, initial, comets_by_id)
        if aim is None:
            continue
        eta = aim[1]
        need = capture_need(target, player, eta, incoming)
        if need <= 0:
            continue
        if ships < need:
            ships = need
            if ships > available:
                continue
            aim = aim_solution(source, target, ships, step, angular_velocity, initial, comets_by_id)
            if aim is None:
                continue
            eta = aim[1]
        if target[OWNER] == -1:
            cap = min(available, max(need + int(target[PROD]) * 3 + 3, int(need * 1.45) + 4))
            if ships > cap:
                ships = cap
                aim = aim_solution(source, target, ships, step, angular_velocity, initial, comets_by_id)
                if aim is None:
                    continue
                eta = aim[1]
        score = target_value(
            source,
            target,
            player,
            ships,
            eta,
            step,
            incoming,
            comets_by_id,
            initial,
            player_count,
        )
        if ships > need + 14 and target[OWNER] == -1:
            score *= 0.92
        if score > best_score:
            best = (int(ships), eta, score)
            best_score = score
    return best


def agent(obs):
    player = int(get(obs, "player", 0))
    step = int(get(obs, "step", 0))
    planets = [list(p) for p in get(obs, "planets", [])]
    fleets = [list(f) for f in get(obs, "fleets", [])]
    initial = {p[ID]: list(p) for p in get(obs, "initial_planets", planets)}
    angular_velocity = float(get(obs, "angular_velocity", 0.035))
    comets_by_id = comet_lookup(get(obs, "comets", []))
    seen_owners = {player}
    for planet in planets:
        if planet[OWNER] >= 0:
            seen_owners.add(int(planet[OWNER]))
    for fleet in fleets:
        if fleet[F_OWNER] >= 0:
            seen_owners.add(int(fleet[F_OWNER]))
    max_owner = max(seen_owners) if seen_owners else player
    player_count = 4 if max_owner >= 3 else max(2, len(seen_owners))

    my_planets = [p for p in planets if p[OWNER] == player]
    if not my_planets:
        return []

    incoming = incoming_map(fleets, planets, step, angular_velocity, initial, comets_by_id)
    opening_actions, opening_spent = opening_moves(
        player,
        step,
        planets,
        my_planets,
        angular_velocity,
        initial,
        comets_by_id,
        incoming,
        player_count,
    )
    moves = list(opening_actions)

    reserves = {p[ID]: reserve_for(p, player, incoming) for p in my_planets}
    available = {
        p[ID]: max(0, int(p[SHIPS]) - reserves[p[ID]] - opening_spent.get(p[ID], 0))
        for p in my_planets
    }

    # Emergency reinforcement gets first claim on spare ships.
    threatened = []
    for planet in my_planets:
        enemy_due = [(ships, eta) for who, ships, eta in incoming.get(planet[ID], []) if who != player]
        if not enemy_due:
            continue
        enemy_due.sort(key=lambda item: item[1])
        ships, eta = enemy_due[0]
        friendly = ships_committed(incoming, planet[ID], player, eta)
        produced = int(planet[PROD] * max(0, eta - 1))
        deficit = ships + 2 - int(planet[SHIPS]) - produced - friendly
        if deficit > 0:
            threatened.append((eta, deficit, planet))

    for eta, deficit, target in sorted(threatened):
        need = int(deficit)
        donors = sorted(
            [p for p in my_planets if p[ID] != target[ID] and available[p[ID]] > 0],
            key=lambda p: dist((p[X], p[Y]), (target[X], target[Y])),
        )
        for donor in donors:
            if need <= 0:
                break
            send = min(available[donor[ID]], need + 1)
            move = legal_verified_move(
                donor, target, send, planets, step, angular_velocity, initial, comets_by_id
            )
            if move is None:
                continue
            action, hit_eta = move
            if hit_eta <= eta + 1:
                moves.append(action)
                available[donor[ID]] -= send
                need -= send

    targets = [p for p in planets if p[OWNER] != player]
    scores = current_scores(planets, fleets)
    my_score = scores[player] if player < len(scores) else 0
    best_enemy_score = max([s for i, s in enumerate(scores) if i != player] or [0])

    for source in sorted(my_planets, key=lambda p: (available[p[ID]], p[PROD]), reverse=True):
        sid = source[ID]
        if available[sid] <= 0:
            continue

        best = None
        for target in targets:
            if target[ID] == sid:
                continue
            if target[ID] in comets_by_id and alive_comet_time(target, comets_by_id) < 8:
                continue
            if target[OWNER] != -1 and (
                step < 240
                or my_score <= best_enemy_score + 250
                or available[sid] < max(45, int(target[SHIPS] * 1.45))
            ):
                continue

            send_choice = choose_send_amount(
                source,
                target,
                player,
                available[sid],
                step,
                angular_velocity,
                initial,
                comets_by_id,
                incoming,
                player_count,
            )
            if send_choice is None:
                continue
            ships, eta, score = send_choice
            if score < 1.35 and not (target[OWNER] != -1 and step > 220 and score > 0.8):
                continue
            if ships > available[sid]:
                continue

            candidate = legal_verified_move(
                source,
                target,
                ships,
                planets,
                step,
                angular_velocity,
                initial,
                comets_by_id,
            )
            if candidate is None:
                continue
            action, hit_eta = candidate
            adjusted_score = score - 0.01 * abs(hit_eta - eta)
            if best is None or adjusted_score > best[0]:
                best = (adjusted_score, action, target[ID], ships, hit_eta)

        if best is None:
            continue

        _, action, target_id, ships, hit_eta = best
        moves.append(action)
        available[sid] -= ships
        incoming.setdefault(target_id, []).append((player, ships, hit_eta))

        if len(moves) >= 12:
            break

    return moves
