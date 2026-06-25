# Orbit Wars v3 foundation
# Based on the public Kaggle notebook
# suntzuisafteru/orbit-wars-1039-2-lb-launch-safety-heuristic.
# Adapted into a single-file submission bot for this workspace.

import math
from typing import NamedTuple

import numpy as np

BOARD_SIZE: float = 100.0
CENTER: np.ndarray = np.array([50.0, 50.0])
SUN_RADIUS: float = 10.0
ROTATION_RADIUS_LIMIT: float = 50.0
MAX_SHIP_SPEED: float = 6.0
COMET_SPEED: float = 4.0

def is_orbiting(planet_xy, planet_radius):
    planet_xy = np.asarray(planet_xy, dtype=float)
    planet_radius = np.asarray(planet_radius, dtype=float)
    orbital_r = np.linalg.norm(planet_xy - CENTER, axis=-1)
    return orbital_r + planet_radius < ROTATION_RADIUS_LIMIT


def effective_omega(planet_xy, planet_radius, game_omega):
    rotates = is_orbiting(planet_xy, planet_radius)
    return np.where(rotates, game_omega, 0.0)


def predict_position_after(current_xy, omega, delta_steps):
    current_xy = np.asarray(current_xy, dtype=float)
    omega = np.asarray(omega, dtype=float)
    delta_steps = np.asarray(delta_steps, dtype=float)
    angle = omega * delta_steps
    rel = current_xy - CENTER
    cos_a = np.cos(angle)
    sin_a = np.sin(angle)
    rx = rel[..., 0] * cos_a - rel[..., 1] * sin_a
    ry = rel[..., 0] * sin_a + rel[..., 1] * cos_a
    rotated = np.stack([rx, ry], axis=-1)
    return rotated + CENTER

def fleet_speed(num_ships):
    n = np.asarray(num_ships, dtype=float)
    n = np.maximum(n, 1.0)
    raw = 1.0 + (MAX_SHIP_SPEED - 1.0) * (np.log(n) / np.log(1000.0)) ** 1.5
    return np.minimum(raw, MAX_SHIP_SPEED)


def fleet_position_after(fleet_xy, fleet_angle, ship_speed, delta_steps):
    fleet_xy = np.asarray(fleet_xy, dtype=float)
    fleet_angle = np.asarray(fleet_angle, dtype=float)
    ship_speed = np.asarray(ship_speed, dtype=float)
    delta_steps = np.asarray(delta_steps, dtype=float)
    dx = np.cos(fleet_angle) * ship_speed * delta_steps
    dy = np.sin(fleet_angle) * ship_speed * delta_steps
    return fleet_xy + np.stack([dx, dy], axis=-1)


def path_hits_sun(from_xy, to_xy):
    from_xy = np.asarray(from_xy, dtype=float)
    to_xy = np.asarray(to_xy, dtype=float)
    seg = to_xy - from_xy
    seg_len_sq = np.sum(seg * seg, axis=-1)
    rel = CENTER - from_xy
    safe_len_sq = np.where(seg_len_sq > 0, seg_len_sq, 1.0)
    t = np.sum(rel * seg, axis=-1) / safe_len_sq
    t = np.clip(t, 0.0, 1.0)
    closest = from_xy + (seg * t[..., None])
    dist = np.linalg.norm(closest - CENTER, axis=-1)
    return dist < SUN_RADIUS


def fleet_collision_step(
    fleet_xy, fleet_angle, ship_speed,
    target_current_xy, target_radius, target_omega,
    max_steps=500, step_resolution=0.5,
):
    fleet_xy = np.asarray(fleet_xy, dtype=float)
    fleet_angle = np.asarray(fleet_angle, dtype=float)
    ship_speed = np.asarray(ship_speed, dtype=float)
    target_current_xy = np.asarray(target_current_xy, dtype=float)
    target_radius = np.asarray(target_radius, dtype=float)
    target_omega = np.asarray(target_omega, dtype=float)

    ts = np.arange(0.0, max_steps + step_resolution, step_resolution)
    fleet_dx = np.cos(fleet_angle)[..., None] * ship_speed[..., None] * ts
    fleet_dy = np.sin(fleet_angle)[..., None] * ship_speed[..., None] * ts
    fleet_pos = fleet_xy[..., None, :] + np.stack([fleet_dx, fleet_dy], axis=-1)
    target_pos = predict_position_after(
        target_current_xy[..., None, :], target_omega[..., None], ts,
    )
    dist = np.linalg.norm(fleet_pos - target_pos, axis=-1)
    hit = dist < target_radius[..., None]
    any_hit = np.any(hit, axis=-1)
    first_idx = np.argmax(hit, axis=-1)
    return np.where(any_hit, ts[first_idx], np.inf)


def first_planet_collision(
    fleet_xy, fleet_angle, ship_speed,
    planet_xys, planet_radii, planet_omegas,
    max_steps=500, step_resolution=0.5, exclude_idx=-1,
):
    fleet_xy = np.asarray(fleet_xy, dtype=float)
    planet_xys = np.asarray(planet_xys, dtype=float)
    planet_radii = np.asarray(planet_radii, dtype=float)
    planet_omegas = np.asarray(planet_omegas, dtype=float)
    m = planet_xys.shape[0]
    if m == 0:
        return -1, float("inf")
    fleet_xys = np.broadcast_to(fleet_xy, (m, 2))
    fleet_angles = np.full((m,), float(fleet_angle))
    speeds = np.full((m,), float(ship_speed))
    steps = fleet_collision_step(
        fleet_xys, fleet_angles, speeds,
        planet_xys, planet_radii, planet_omegas,
        max_steps=max_steps, step_resolution=step_resolution,
    )
    if 0 <= exclude_idx < m:
        steps = steps.copy()
        steps[exclude_idx] = np.inf
    if not np.any(np.isfinite(steps)):
        return -1, float("inf")
    idx = int(np.argmin(steps))
    return idx, float(steps[idx])

class InterceptSolution(NamedTuple):
    angle: np.ndarray
    arrival_step: np.ndarray
    feasible: np.ndarray


def solve_intercept(
    from_xy, target_current_xy, target_omega, ship_speed,
    max_steps=500, tol=0.5, max_iters=40,
    source_radius=0.0, first_step_lag=0,
):
    from_xy = np.asarray(from_xy, dtype=float)
    target_current_xy = np.asarray(target_current_xy, dtype=float)
    target_omega = np.asarray(target_omega, dtype=float)
    ship_speed = np.asarray(ship_speed, dtype=float)
    source_radius = np.asarray(source_radius, dtype=float)

    safe_speed = np.maximum(ship_speed, 1e-12)
    radius_pad = (source_radius + 0.1) / safe_speed

    delta = target_current_xy - from_xy
    dt = np.linalg.norm(delta, axis=-1) / safe_speed

    def _rot_time(dt_val):
        return np.maximum(dt_val - radius_pad - float(first_step_lag), 0.0)

    converged = np.zeros_like(dt, dtype=bool)
    for _ in range(max_iters):
        target_pos = predict_position_after(target_current_xy, target_omega, _rot_time(dt))
        new_delta = target_pos - from_xy
        new_dt = np.linalg.norm(new_delta, axis=-1) / safe_speed
        converged = np.abs(new_dt - dt) < tol
        dt = new_dt
        if np.all(converged):
            break

    target_pos = predict_position_after(target_current_xy, target_omega, _rot_time(dt))
    aim_vec = target_pos - from_xy
    angle = np.arctan2(aim_vec[..., 1], aim_vec[..., 0])
    sun_safe = ~path_hits_sun(from_xy, target_pos)
    feasible = converged & (dt <= max_steps) & sun_safe
    arrival = np.where(feasible, dt, np.inf)
    return InterceptSolution(angle=angle, arrival_step=arrival, feasible=feasible)


def solve_intercept_comet(from_xy, comet_path, path_index, ship_speed, speed_tol_frac=0.1):
    from_xy = np.asarray(from_xy, dtype=float)
    comet_path = np.asarray(comet_path, dtype=float)
    ship_speed = float(ship_speed)
    if ship_speed <= 0 or len(comet_path) == 0:
        return InterceptSolution(
            angle=np.array(0.0), arrival_step=np.array(np.inf), feasible=np.array(False),
        )
    remaining = len(comet_path) - int(path_index)
    if remaining <= 1:
        return InterceptSolution(
            angle=np.array(0.0), arrival_step=np.array(np.inf), feasible=np.array(False),
        )
    tol = speed_tol_frac * ship_speed
    for dt in range(1, remaining):
        target_pos = comet_path[int(path_index) + dt]
        dist = float(np.linalg.norm(target_pos - from_xy))
        required = dist / dt
        if abs(required - ship_speed) > tol:
            continue
        if bool(path_hits_sun(from_xy, target_pos)):
            continue
        aim = target_pos - from_xy
        angle = float(math.atan2(float(aim[1]), float(aim[0])))
        return InterceptSolution(
            angle=np.array(angle), arrival_step=np.array(float(dt)), feasible=np.array(True),
        )
    return InterceptSolution(
        angle=np.array(0.0), arrival_step=np.array(np.inf), feasible=np.array(False),
    )

NEUTRAL_OWNER = -1


def ships_needed_to_capture(garrison, production, owner_id, target_player_id, arrival_step):
    garrison = np.asarray(garrison, dtype=float)
    production = np.asarray(production, dtype=float)
    owner_id = np.asarray(owner_id, dtype=int)
    arrival_step = np.asarray(arrival_step, dtype=float)
    is_friendly = owner_id == target_player_id
    is_neutral = owner_id == NEUTRAL_OWNER
    needed_neutral = garrison + 1
    needed_enemy = garrison + production * arrival_step + 1
    needed = np.where(is_neutral, needed_neutral, needed_enemy)
    needed = np.where(is_friendly, 0.0, needed)
    return np.ceil(needed).astype(int)


def build_arrival_ledger(fleets, ids, xys, radii, omegas, horizon):
    ledger = {int(pid): [] for pid in ids}
    if len(fleets) == 0:
        return ledger
    for f in fleets:
        fleet_xy = np.array([f[2], f[3]], dtype=float)
        fleet_angle = float(f[4])
        fleet_n = int(f[6])
        speed = float(fleet_speed(fleet_n))
        target_idx, eta = first_planet_collision(
            fleet_xy, fleet_angle, speed,
            xys, radii, omegas,
            max_steps=horizon,
        )
        if target_idx < 0 or not math.isfinite(eta):
            continue
        impact_xy = fleet_position_after(fleet_xy, fleet_angle, speed, eta)
        if bool(path_hits_sun(fleet_xy, impact_xy)):
            continue
        ledger.setdefault(int(ids[target_idx]), []).append(
            (float(eta), int(f[1]), int(fleet_n))
        )
    return ledger


def resolve_arrival_group(owner, garrison, arrivals):
    by_owner: dict[int, int] = {}
    for _, attacker_owner, n in arrivals:
        by_owner[int(attacker_owner)] = by_owner.get(int(attacker_owner), 0) + int(n)
    if not by_owner:
        return int(owner), float(max(0.0, garrison))

    ranked = sorted(by_owner.items(), key=lambda item: item[1], reverse=True)
    top_owner, top_ships = ranked[0]
    if len(ranked) > 1 and ranked[1][1] == top_ships:
        return int(owner), float(max(0.0, garrison))
    if int(owner) == int(top_owner):
        return int(owner), float(max(0.0, garrison + top_ships))

    garrison = float(garrison) - float(top_ships)
    if garrison < 0:
        return int(top_owner), float(-garrison)
    return int(owner), float(max(0.0, garrison))


def simulate_planet_timeline(owner, garrison, production, arrivals, player, horizon):
    horizon = max(0, int(math.ceil(float(horizon))))
    by_turn: dict[int, list[tuple[float, int, int]]] = {}
    for eta, attacker_owner, n in arrivals:
        if n <= 0:
            continue
        turn = max(1, int(math.ceil(float(eta))))
        if turn > horizon:
            continue
        by_turn.setdefault(turn, []).append((float(eta), int(attacker_owner), int(n)))

    owner = int(owner)
    garrison = float(garrison)
    production = int(production)
    owner_at = {0: owner}
    ships_at = {0: float(max(0.0, garrison))}
    fall_turn = None

    for turn in range(1, horizon + 1):
        if owner != NEUTRAL_OWNER:
            garrison += production
        prev_owner = owner
        group = by_turn.get(turn, [])
        if group:
            owner, garrison = resolve_arrival_group(owner, garrison, group)
            if prev_owner == player and owner != player and fall_turn is None:
                fall_turn = turn
        owner_at[turn] = owner
        ships_at[turn] = float(max(0.0, garrison))

    keep_needed = 0
    holds_full = True
    if owner_at[0] == player:
        def survives_with_keep(keep):
            sim_owner = int(owner_at[0])
            sim_garrison = float(keep)
            for turn in range(1, horizon + 1):
                if sim_owner != NEUTRAL_OWNER:
                    sim_garrison += production
                group = by_turn.get(turn, [])
                if group:
                    sim_owner, sim_garrison = resolve_arrival_group(
                        sim_owner, sim_garrison, group
                    )
                    if sim_owner != player:
                        return False
            return sim_owner == player

        if survives_with_keep(int(ships_at[0])):
            lo, hi = 0, int(ships_at[0])
            while lo < hi:
                mid = (lo + hi) // 2
                if survives_with_keep(mid):
                    hi = mid
                else:
                    lo = mid + 1
            keep_needed = lo
        else:
            holds_full = False

    return {
        "owner_at": owner_at,
        "ships_at": ships_at,
        "keep_needed": int(keep_needed),
        "holds_full": bool(holds_full),
        "fall_turn": fall_turn,
        "horizon": horizon,
    }


def state_at_timeline(timeline, arrival_step):
    turn = max(0, int(math.ceil(float(arrival_step))))
    turn = min(turn, int(timeline["horizon"]))
    return (
        int(timeline["owner_at"].get(turn, timeline["owner_at"][timeline["horizon"]])),
        float(timeline["ships_at"].get(turn, timeline["ships_at"][timeline["horizon"]])),
    )


def projected_capture_need(j, player, arrival, ids, owners, ships, prods, ledger):
    target_id = int(ids[j])
    timeline = simulate_planet_timeline(
        int(owners[j]), int(ships[j]), int(prods[j]),
        ledger.get(target_id, []), int(player), arrival,
    )
    owner, projected_ships = state_at_timeline(timeline, arrival)
    if owner == player:
        return 0, owner, projected_ships
    return int(math.ceil(projected_ships)) + 1, owner, projected_ships


def hold_fraction_after_capture(j, player, arrival, sent, ids, owners, ships, prods, ledger, hold_horizon):
    target_id = int(ids[j])
    horizon = int(math.ceil(float(arrival))) + int(hold_horizon)
    extra = list(ledger.get(target_id, [])) + [(float(arrival), int(player), int(sent))]
    timeline = simulate_planet_timeline(
        int(owners[j]), int(ships[j]), int(prods[j]),
        extra, int(player), horizon,
    )
    start = max(1, int(math.ceil(float(arrival))))
    owned = 0
    checked = 0
    for turn in range(start, horizon + 1):
        checked += 1
        if int(timeline["owner_at"].get(turn, NEUTRAL_OWNER)) == player:
            owned += 1
    if checked <= 0:
        return 1.0
    return owned / checked


def score_totals(owners, ships, fleets, player_count):
    scores = [0 for _ in range(player_count)]
    for owner, n in zip(owners, ships):
        owner = int(owner)
        if 0 <= owner < player_count:
            scores[owner] += int(n)
    for f in fleets:
        owner = int(f[1])
        if 0 <= owner < player_count:
            scores[owner] += int(f[6])
    return scores

AGENT_CODE = "AIN"
AGENT_NAME = "All-In (may18 launch-safety champion)"

HORIZON = 30
MIN_RESERVE = 0
DEFENSE_HORIZON = 80
ARRIVAL_LEDGER_HORIZON = 150
TIMELINE_HOLD_HORIZON = 18
TOTAL_STEPS = 500
SCORE_FLOOR = 2.4
PV_SCORE_FLOOR = 3.25
ENEMY_DENIAL_BONUS = 2.0
LAUNCH_SAFETY_FLOOR = 0.4
LAUNCH_SAFETY_SCALE = 30.0
HAMMER_MIN_STEP = 85
HAMMER_MIN_SOURCE = 8
HAMMER_MAX_SOURCES = 4
HAMMER_MAX_SPREAD = 18
HAMMER_SCORE_FLOOR = 7.0


def _obs_field(obs, name, default):
    return obs.get(name, default) if isinstance(obs, dict) else getattr(obs, name, default)


def _comet_path_map(obs):
    groups = _obs_field(obs, "comets", [])
    out: dict[int, tuple] = {}
    for group in groups:
        idx = int(group["path_index"] if isinstance(group, dict) else group.path_index)
        pids = group["planet_ids"] if isinstance(group, dict) else group.planet_ids
        paths = group["paths"] if isinstance(group, dict) else group.paths
        for i, pid in enumerate(pids):
            path = np.asarray(paths[i], dtype=float)
            remaining = max(0, len(path) - idx)
            out[int(pid)] = (path, idx, remaining)
    return out


def agent(obs):
    planets = _obs_field(obs, "planets", [])
    fleets = _obs_field(obs, "fleets", [])
    my_player = _obs_field(obs, "player", 0)
    step = int(_obs_field(obs, "step", 0))
    omega = _obs_field(obs, "angular_velocity", 0.0)
    comet_ids = set(_obs_field(obs, "comet_planet_ids", []))

    rows = list(planets)
    if not rows:
        return []

    ids = np.array([p[0] for p in rows], dtype=int)
    owners = np.array([p[1] for p in rows], dtype=int)
    xys = np.array([[p[2], p[3]] for p in rows], dtype=float)
    radii = np.array([p[4] for p in rows], dtype=float)
    ships = np.array([p[5] for p in rows], dtype=int)
    prods = np.array([p[6] for p in rows], dtype=int)
    omegas = effective_omega(xys, radii, omega)
    is_comet = np.array([int(pid) in comet_ids for pid in ids])
    # Comets follow precomputed paths, not omega-based rotation; treat as static
    # obstacles for the planet-collision sweep.
    omegas = np.where(is_comet, 0.0, omegas)
    comet_paths = _comet_path_map(obs)

    seen_owners = {int(my_player)}
    seen_owners.update(int(owner) for owner in owners if int(owner) >= 0)
    seen_owners.update(int(f[1]) for f in fleets if int(f[1]) >= 0)
    max_owner = max(seen_owners) if seen_owners else int(my_player)
    player_count = 4 if max_owner >= 3 else max(2, len(seen_owners))
    owner_scores = score_totals(owners, ships, fleets, player_count)
    my_score = owner_scores[int(my_player)] if int(my_player) < player_count else 0
    enemy_scores = [
        (pid, score) for pid, score in enumerate(owner_scores) if pid != int(my_player)
    ]
    leader_owner, leader_score = max(enemy_scores, key=lambda item: item[1]) if enemy_scores else (-1, 0)

    mine_mask = owners == my_player
    target_mask = ~mine_mask
    if not np.any(mine_mask):
        return []
    mine_idx = np.where(mine_mask)[0]

    arrival_ledger = build_arrival_ledger(
        fleets, ids, xys, radii, omegas, ARRIVAL_LEDGER_HORIZON
    )
    base_timelines = {
        int(ids[i]): simulate_planet_timeline(
            int(owners[i]), int(ships[i]), int(prods[i]),
            arrival_ledger.get(int(ids[i]), []), int(my_player), DEFENSE_HORIZON,
        )
        for i in range(len(ids))
    }

    # ---- Defensive reserves: how much garrison each of my planets must keep ----
    reserves: dict[int, int] = {}
    for f in fleets:
        if f[1] == my_player:
            continue
        fleet_xy = np.array([f[2], f[3]], dtype=float)
        fleet_angle = float(f[4])
        fleet_n = int(f[6])
        speed = float(fleet_speed(fleet_n))
        best_i = -1
        best_t = math.inf
        for i in mine_idx:
            t = float(fleet_collision_step(
                fleet_xy, fleet_angle, speed,
                xys[i], radii[i], omegas[i],
                max_steps=DEFENSE_HORIZON,
            ))
            if t < best_t:
                best_t = t
                best_i = int(i)
        if best_i < 0:
            continue
        # (1) Sun-doomed: enemy fleet dies in the sun before arrival.
        arrival_xy = fleet_position_after(fleet_xy, fleet_angle, speed, best_t)
        if bool(path_hits_sun(fleet_xy, arrival_xy)):
            continue
        grow = int(prods[best_i]) * int(round(best_t))
        shortfall = fleet_n - grow
        # (2) Planet-doomed: short by more than current ships; planet falls regardless.
        if shortfall > int(ships[best_i]):
            continue
        reserves[int(ids[best_i])] = max(reserves.get(int(ids[best_i]), 0), shortfall)

    # ---- (3) Reinforce doomed high-production planets ----
    ships_avail = ships.copy()
    reinforce_moves: list[list] = []
    reinforced: set[int] = set()
    for f in fleets:
        if f[1] == my_player:
            continue
        fxy = np.array([f[2], f[3]], dtype=float)
        fang = float(f[4])
        fn = int(f[6])
        sp = float(fleet_speed(fn))
        bi = -1
        bt = math.inf
        for i in mine_idx:
            t = float(fleet_collision_step(
                fxy, fang, sp,
                xys[i], radii[i], omegas[i],
                max_steps=DEFENSE_HORIZON,
            ))
            if t < bt:
                bt = t
                bi = int(i)
        if bi < 0 or int(prods[bi]) < 2:
            continue
        if bool(path_hits_sun(fxy, fleet_position_after(fxy, fang, sp, bt))):
            continue
        gr = int(prods[bi]) * int(round(bt))
        sf = fn - gr
        if sf <= int(ships_avail[bi]):
            continue
        tpid = int(ids[bi])
        if tpid in reinforced:
            continue
        gap = sf - int(ships_avail[bi]) + 1
        best_k = -1
        best_k_angle = 0.0
        best_k_t = math.inf
        for k in mine_idx:
            if int(k) == bi:
                continue
            spare = int(ships_avail[k]) - MIN_RESERVE
            if spare < gap:
                continue
            send_speed = float(fleet_speed(gap))
            sol = solve_intercept(xys[k], xys[bi], omegas[bi], send_speed)
            if not bool(sol.feasible) or float(sol.arrival_step) >= bt:
                continue
            if float(sol.arrival_step) < best_k_t:
                best_k_t = float(sol.arrival_step)
                best_k = int(k)
                best_k_angle = float(sol.angle)
        if best_k >= 0:
            reinforce_moves.append([int(ids[best_k]), best_k_angle, int(gap)])
            ships_avail[best_k] -= gap
            reinforced.add(tpid)

    if not np.any(target_mask):
        return reinforce_moves
    target_idx = np.where(target_mask)[0]

    # ---- Launch-safety: distance from each of my planets to nearest enemy ----
    # Threats = enemy-owned planets + enemy fleet CURRENT POSITIONS. The latter
    # is the may18 promotion delta (~+100 Elo).
    enemy_owned_mask = (owners >= 0) & (owners != my_player) & (~is_comet)
    threats: list[np.ndarray] = []
    if np.any(enemy_owned_mask):
        threats.append(xys[enemy_owned_mask])
    enemy_fleet_xys = np.array(
        [[f[2], f[3]] for f in fleets if f[1] != my_player], dtype=float,
    )
    if len(enemy_fleet_xys) > 0:
        threats.append(enemy_fleet_xys)
    if threats:
        all_threats = np.vstack(threats)
        d_mine = np.linalg.norm(
            xys[mine_idx, None, :] - all_threats[None, :, :], axis=2
        ).min(axis=1)
        safety_by_mine = np.clip(
            d_mine / LAUNCH_SAFETY_SCALE, LAUNCH_SAFETY_FLOOR, 1.0
        )
    else:
        safety_by_mine = np.ones(len(mine_idx), dtype=float)
    safety_lookup = {int(mi): float(safety_by_mine[k]) for k, mi in enumerate(mine_idx)}

    # ---- Offensive scoring ----
    candidates = []
    hammer_options: dict[int, list[tuple[float, int, float, int, int]]] = {}
    remaining_steps = max(1, TOTAL_STEPS - step)
    rotating_now = is_orbiting(xys, radii)
    enemy_planet_idx = np.where((owners >= 0) & (owners != my_player) & (~is_comet))[0]
    for j in target_idx:
        target_is_comet = bool(is_comet[j])
        comet_info = comet_paths.get(int(ids[j])) if target_is_comet else None
        if target_is_comet and (comet_info is None or comet_info[2] <= 1):
            continue
        for i in mine_idx:
            reserve = max(reserves.get(int(ids[i]), 0), MIN_RESERVE)
            available = int(ships_avail[i]) - reserve
            if available < 1:
                continue

            rough_need = int(ships[j]) + 1
            if int(owners[j]) not in (NEUTRAL_OWNER, int(my_player)):
                rough_need += int(prods[j]) * 18

            if target_is_comet:
                send_probes = {available}
            elif int(owners[j]) == NEUTRAL_OWNER:
                efficient = min(
                    available,
                    max(rough_need + int(prods[j]) * 4 + 5, int(rough_need * 1.45) + 3),
                )
                send_probes = {max(1, efficient), available}
                if step > 90:
                    send_probes.add(max(1, min(available, int(available * 0.65))))
            else:
                pressure = min(
                    available,
                    max(rough_need + int(prods[j]) * 5 + 8, int(available * 0.8)),
                )
                send_probes = {available, max(1, pressure)}

            # Submission path keeps the proven all-in launch behavior; smaller
            # probes were too slow against aggressive expanders in local gauntlets.
            send_probes = {available}

            for send in sorted(send_probes, reverse=True):
                send = int(max(1, min(available, send)))
                speed = float(fleet_speed(send))

                if target_is_comet:
                    path, pidx, lifetime = comet_info
                    sol = solve_intercept_comet(xys[i], path, pidx, speed)
                else:
                    sol = solve_intercept(xys[i], xys[j], omegas[j], speed)
                if not bool(sol.feasible):
                    continue
                arrival = float(sol.arrival_step)

                # Sweep filter: another planet may eclipse the target before we arrive.
                first_idx, _ = first_planet_collision(
                    xys[i], float(sol.angle), speed,
                    xys, radii, omegas,
                    max_steps=int(arrival) + 5,
                    exclude_idx=int(i),
                )
                if first_idx != int(j):
                    continue

                needed = int(ships_needed_to_capture(
                    int(ships[j]), int(prods[j]), int(owners[j]),
                    int(my_player), arrival,
                ))
                projected_ships = float(ships[j])

                if (
                    int(owners[j]) not in (NEUTRAL_OWNER, int(my_player))
                    and send == available
                    and available >= HAMMER_MIN_SOURCE
                    and needed > 0
                ):
                    hammer_options.setdefault(int(j), []).append(
                        (arrival, int(i), float(sol.angle), int(send), int(needed))
                    )

                if needed <= 0 or needed > send:
                    continue

                if target_is_comet:
                    rem_after = max(0, comet_info[2] - 1 - int(arrival))
                    effective_horizon = min(HORIZON, rem_after)
                else:
                    effective_horizon = min(175, max(0, remaining_steps - int(arrival)))
                if effective_horizon <= 0:
                    continue

                value = float(prods[j]) * float(effective_horizon)
                value += 0.12 * max(0.0, projected_ships)

                if int(owners[j]) == NEUTRAL_OWNER:
                    value *= 1.25
                    if step < 120:
                        value *= 1.18
                elif int(owners[j]) != int(my_player):
                    value *= ENEMY_DENIAL_BONUS
                    if step < 100:
                        value *= 0.58
                    if player_count >= 4 and int(owners[j]) == int(leader_owner):
                        if leader_score > my_score:
                            value *= 1.55
                        else:
                            value *= 1.18
                    elif player_count >= 4 and leader_score > 0:
                        target_owner_score = owner_scores[int(owners[j])]
                        if target_owner_score < 0.55 * leader_score:
                            value *= 0.82

                if target_is_comet:
                    value *= 0.58
                elif not bool(rotating_now[j]):
                    value *= 1.08

                nearest_my = float(np.linalg.norm(xys[mine_idx] - xys[j], axis=1).min())
                if len(enemy_planet_idx) > 0:
                    nearest_enemy = float(
                        np.linalg.norm(xys[enemy_planet_idx] - xys[j], axis=1).min()
                    )
                    if int(owners[j]) == NEUTRAL_OWNER:
                        contest_margin = 9.0 if step < 90 else 4.0
                        if nearest_enemy + contest_margin < nearest_my:
                            value *= 0.68
                        elif nearest_my + 4.0 < nearest_enemy:
                            value *= 1.10
                    elif nearest_enemy < 18.0:
                        value *= 0.86

                hold_fraction = 1.0

                distance = float(np.linalg.norm(xys[i] - xys[j]))
                cost = float(send) + 0.65 * max(arrival, 1.0) + 0.03 * distance
                score = value / max(cost, 1.0)
                score *= safety_lookup[int(i)]
                score *= 0.55 + 0.45 * hold_fraction

                # Keep the old short-horizon score as a useful tactical backstop.
                short_score = (
                    int(prods[j]) * min(HORIZON, effective_horizon) - needed
                ) / max(arrival, 1.0)
                if int(owners[j]) >= 0:
                    short_score *= ENEMY_DENIAL_BONUS
                score = max(score, short_score * safety_lookup[int(i)])

                floor = SCORE_FLOOR
                if int(owners[j]) == NEUTRAL_OWNER:
                    floor = 1.15 if step < 120 else 2.0
                if score < floor:
                    continue
                candidates.append((score, int(j), int(i), float(sol.angle), int(send)))

    candidates.sort(reverse=True)
    moves = list(reinforce_moves)
    used_planets: set[int] = {int(m[0]) for m in reinforce_moves}
    locked_targets: set[int] = set()

    # ---- Hammer attack: combine multiple sources against a valuable enemy ----
    if step >= HAMMER_MIN_STEP or player_count >= 4:
        best_hammer = None
        for j, pieces in hammer_options.items():
            if int(owners[j]) in (NEUTRAL_OWNER, int(my_player)):
                continue
            usable = [
                piece for piece in pieces
                if int(ids[piece[1]]) not in used_planets and piece[3] >= HAMMER_MIN_SOURCE
            ]
            if len(usable) < 2:
                continue
            usable.sort(key=lambda item: (item[0], -item[3]))

            for anchor_arrival, *_ in usable:
                cluster = [
                    piece for piece in usable
                    if abs(float(piece[0]) - float(anchor_arrival)) <= HAMMER_MAX_SPREAD
                ][:HAMMER_MAX_SOURCES]
                if len(cluster) < 2:
                    continue
                max_arrival = max(float(piece[0]) for piece in cluster)
                combined = sum(int(piece[3]) for piece in cluster)
                needed, _, _ = projected_capture_need(
                    int(j), int(my_player), max_arrival,
                    ids, owners, ships, prods, arrival_ledger,
                )
                margin = int(prods[j]) * 4 + 6
                if combined < needed + margin:
                    continue
                hold_fraction = hold_fraction_after_capture(
                    int(j), int(my_player), max_arrival, combined,
                    ids, owners, ships, prods, arrival_ledger, TIMELINE_HOLD_HORIZON,
                )
                if hold_fraction < 0.42:
                    continue

                window = min(160, max(1, remaining_steps - int(max_arrival)))
                value = float(prods[j]) * window * ENEMY_DENIAL_BONUS
                if player_count >= 4 and int(owners[j]) == int(leader_owner):
                    value *= 1.45 if leader_score > my_score else 1.15
                value *= 0.65 + 0.35 * hold_fraction
                score = value / max(1.0, combined + 0.7 * max_arrival)
                if score < HAMMER_SCORE_FLOOR:
                    continue
                if best_hammer is None or score > best_hammer[0]:
                    best_hammer = (score, int(j), cluster)

        if best_hammer is not None:
            _, target_j, cluster = best_hammer
            locked_targets.add(target_j)
            for _, i, angle, send, _ in cluster:
                used_planets.add(int(ids[i]))
                moves.append([int(ids[i]), float(angle), int(send)])

    for score, j, i, angle, needed in candidates:
        if int(ids[i]) in used_planets:
            continue
        if j in locked_targets:
            continue
        used_planets.add(int(ids[i]))
        locked_targets.add(j)
        moves.append([int(ids[i]), float(angle), int(needed)])
    return moves
