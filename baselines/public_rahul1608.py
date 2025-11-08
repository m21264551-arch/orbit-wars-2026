# Auto-extracted by tools/extract_public_agents.py.
# Source notebook: public_kernels/rahul1608/orbit-wars-advanced-agent-target-1608-6.ipynb

import math
import time
import random
from collections import defaultdict
from typing import List, Tuple, Dict, Optional

class Planet:
    __slots__ = ("id", "owner", "x", "y", "radius", "ships", "production")
    def __init__(self, raw_data):
        self.id, self.owner, self.x, self.y, self.radius, self.ships, self.production = raw_data
    def get_distance(self, target) -> float:
        return math.hypot(self.x - target.x, self.y - target.y)
    def distance_to_coord(self, target_x: float, target_y: float) -> float:
        return math.hypot(self.x - target_x, self.y - target_y)
    def angle_to_coord(self, target_x: float, target_y: float) -> float:
        return math.atan2(target_y - self.y, target_x - self.x)

class Fleet:
    __slots__ = ("id", "owner", "x", "y", "angle", "source_planet_id", "ships")
    def __init__(self, raw_data):
        self.id, self.owner, self.x, self.y, self.angle, self.source_planet_id, self.ships = raw_data

class GameState:
    def __init__(self, obs):
        get_attr = lambda k: getattr(obs, k, None) if hasattr(obs, k) else (obs.get(k) if isinstance(obs, dict) else None)
        self.my_id = get_attr("player") or 0
        self.ang_vel = get_attr("angular_velocity") or 0.027
        self.step = get_attr("step") or 0
        self.planets = [Planet(p) for p in (get_attr("planets") or [])]
        self.fleets = [Fleet(f) for f in (get_attr("fleets") or [])]
        self.planet_map = {p.id: p for p in self.planets}
        self.my_planets = [p for p in self.planets if p.owner == self.my_id]
        self.enemy_planets = [p for p in self.planets if p.owner not in (-1, self.my_id)]
        self.neutral_planets = [p for p in self.planets if p.owner == -1]
        self.enemy_ids = list({p.owner for p in self.enemy_planets})

    def get_planet(self, p_id: int) -> Optional[Planet]:
        return self.planet_map.get(p_id)

    def predict_target(self, fleet: Fleet) -> Optional[int]:
        best_target = None
        min_angle_delta = 0.30
        closest_distance = float('inf')
        for p in self.planets:
            calc_angle = math.atan2(p.y - fleet.y, p.x - fleet.x)
            angle_delta = abs((calc_angle - fleet.angle + math.pi) % (2 * math.pi) - math.pi)
            if angle_delta < min_angle_delta:
                dist = math.hypot(p.x - fleet.x, p.y - fleet.y)
                if dist < closest_distance:
                    closest_distance = dist
                    best_target = p.id
        return best_target

def get_fleet_speed(ships: int) -> float:
    return min(1.0 + float(ships // 20), 6.0)

def check_sun_collision(src_x: float, src_y: float, travel_angle: float) -> bool:
    dx, dy = math.cos(travel_angle), math.sin(travel_angle)
    t = (50.0 - src_x) * dx + (50.0 - src_y) * dy
    if t < 0.0: return False
    return math.hypot(src_x + t * dx - 50.0, src_y + t * dy - 50.0) < 7.0

def agent(obs, config=None):
    try:
        state = GameState(obs)
        if not state.my_planets: return []
        moves = []
        for src in state.my_planets:
            if src.ships > 15:
                targets = sorted(state.neutral_planets + state.enemy_planets, key=lambda p: src.get_distance(p))
                if targets:
                    t = targets[0]
                    ang = src.angle_to_coord(t.x, t.y)
                    if not check_sun_collision(src.x, src.y, ang):
                        moves.append([src.id, float(ang), int(src.ships // 2)])
        return moves
    except:
        return []
