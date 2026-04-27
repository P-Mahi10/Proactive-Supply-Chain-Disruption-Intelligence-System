"""
Supply Chain Simulation Model  —  v2  (Route Comparison Edition)
=================================================================
New in v2:
  - RouteGraph: precomputes all realistic candidate routes for 27-port network
  - compare_routes(): simulates all candidates, ranks by delay + risk
  - Existing run() and run_batch() unchanged — fully backward compatible

Usage:
    sim = SimulationModel()
    sim.load_calibration("calibration.json")

    # Single route simulation (unchanged)
    result = sim.run(origin_port_id="port776", destination_port_id="port1114", ...)

    # Route comparison (new)
    comparison = sim.compare_routes(
        origin_port_id      = "port815",   # New York
        destination_port_id = "port442",   # Kolkata
        risk_scores         = {"port815": 0.3, "port192": 0.71},
        season              = "summer",
        n_runs              = 500,
    )
    print(comparison.summary())
"""

import json
import math
import warnings
import numpy as np
import pandas as pd
import simpy
from dataclasses import dataclass, field, asdict
from typing import Optional
from scipy.stats import lognorm

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────
# PORT REGISTRY  (IMF PortWatch verified IDs)
# ─────────────────────────────────────────────────────────────────

PORTS = {
    "port776":  {"name": "JNPT",           "country": "India",        "lat": 18.95, "lon":  72.95},
    "port777":  {"name": "Mundra",          "country": "India",        "lat": 22.74, "lon":  69.71},
    "port235":  {"name": "Chennai",         "country": "India",        "lat": 13.08, "lon":  80.30},
    "port1367": {"name": "Visakhapatnam",   "country": "India",        "lat": 17.69, "lon":  83.29},
    "port442":  {"name": "Kolkata",         "country": "India",        "lat": 22.02, "lon":  88.06},
    "port583":  {"name": "Cochin",          "country": "India",        "lat":  9.96, "lon":  76.26},
    "port907":  {"name": "Pipavav",         "country": "India",        "lat": 20.90, "lon":  71.50},
    "port1188": {"name": "Shanghai",        "country": "China",        "lat": 30.62, "lon": 122.06},
    "port1201": {"name": "Singapore",       "country": "Singapore",    "lat":  1.27, "lon": 103.78},
    "port824":  {"name": "Ningbo",          "country": "China",        "lat": 29.94, "lon": 122.02},
    "port1189": {"name": "Shenzhen",        "country": "China",        "lat": 22.50, "lon": 113.88},
    "port1065": {"name": "Busan",           "country": "South Korea",  "lat": 35.10, "lon": 129.04},
    "port474":  {"name": "Hong Kong",       "country": "Hong Kong",    "lat": 22.33, "lon": 114.13},
    "port1069": {"name": "Qingdao",         "country": "China",        "lat": 36.01, "lon": 120.20},
    "port1297": {"name": "Tianjin",         "country": "China",        "lat": 38.98, "lon": 117.76},
    "port1114": {"name": "Rotterdam",       "country": "Netherlands",  "lat": 51.95, "lon":   4.05},
    "port306":  {"name": "Jebel Ali",       "country": "UAE",          "lat": 25.00, "lon":  55.06},
    "port446":  {"name": "Hamburg",         "country": "Germany",      "lat": 53.53, "lon":   9.95},
    "port815":  {"name": "New York",        "country": "USA",          "lat": 40.67, "lon": -74.04},
    "port664":  {"name": "Los Angeles",     "country": "USA",          "lat": 33.73, "lon":-118.26},
    "port1269": {"name": "Tanjung Pelepas", "country": "Malaysia",     "lat":  1.36, "lon": 103.55},
    "port254":  {"name": "Colombo",         "country": "Sri Lanka",    "lat":  6.94, "lon":  79.84},
    "port192":  {"name": "Port Said",       "country": "Egypt",        "lat": 31.26, "lon":  32.31},
    "port57":   {"name": "Antwerp",         "country": "Belgium",      "lat": 51.28, "lon":   4.34},
    "port343":  {"name": "Felixstowe",      "country": "UK",           "lat": 51.95, "lon":   1.31},
    "port1417": {"name": "Yokohama",        "country": "Japan",        "lat": 35.45, "lon": 139.66},
    "port543":  {"name": "Karachi",         "country": "Pakistan",     "lat": 24.81, "lon":  66.97},
}

# Hub classification by corridor
HUBS = {
    "indian_ocean":   ["port254", "port306"],        # Colombo, Jebel Ali
    "se_asia":        ["port1201", "port1269"],       # Singapore, Tanjung Pelepas
    "east_asia":      ["port474", "port1065"],        # Hong Kong, Busan
    "europe":         ["port1114", "port57"],         # Rotterdam, Antwerp
    "suez_gateway":   ["port192"],                    # Port Said
    "transpacific":   ["port664", "port1417"],        # LA, Yokohama
    "middle_east":    ["port306"],                    # Jebel Ali
}

ALL_HUBS = {p for hubs in HUBS.values() for p in hubs}

CARGO_SPEEDS = {
    "container": 22.0, "bulk": 14.0,
    "liquid":    13.0, "breakbulk": 15.0, "roro": 19.0,
}

DISRUPTION_TYPES = ["none", "congestion", "weather", "strike", "equipment"]


# ─────────────────────────────────────────────────────────────────
# ROUTE GRAPH  — precomputed candidate routes for 27-port network
# ─────────────────────────────────────────────────────────────────

def _haversine(p1: str, p2: str) -> float:
    a, b = PORTS[p1], PORTS[p2]
    R = 6371.0
    la1, lo1 = math.radians(a["lat"]), math.radians(a["lon"])
    la2, lo2 = math.radians(b["lat"]), math.radians(b["lon"])
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return R * 2 * math.asin(math.sqrt(d))


def _route_distance(route: list) -> float:
    return sum(_haversine(route[i], route[i+1]) for i in range(len(route)-1))


def _is_geographically_sensible(route: list) -> bool:
    """
    Reject routes where an intermediate hub is further from both
    origin and destination than origin is from destination — i.e.
    routes that backtrack badly.
    """
    if len(route) <= 2:
        return True
    direct = _haversine(route[0], route[-1])
    total  = _route_distance(route)
    # Allow up to 60% detour — catches transshipment overhead
    return total <= direct * 1.60


class RouteGraph:
    """
    Precomputes 3-5 realistic candidate routes for any O-D pair
    in the 27-port network based on geographic logic and trade corridors.
    """

    # Corridor definitions: which hubs are natural for each region pair
    _CORRIDOR_HUBS = {
        # (region_a, region_b): [hub_sequence_options]
        ("Americas",     "South Asia"):    [["port192"],                ["port306", "port254"], ["port664", "port1201"]],
        ("Americas",     "SE Asia"):       [["port664", "port1201"],    ["port1417", "port474"]],
        ("Americas",     "East Asia"):     [["port664"],                ["port1417"]],
        ("Americas",     "Europe"):        [],  # direct
        ("Americas",     "Middle East"):   [["port192"]],
        ("Europe",       "South Asia"):    [["port192"],                ["port192", "port306"], ["port192", "port254"]],
        ("Europe",       "SE Asia"):       [["port192", "port1201"],    ["port192", "port254", "port1201"]],
        ("Europe",       "East Asia"):     [["port192", "port1201"],    ["port192", "port474"]],
        ("Europe",       "Middle East"):   [["port192"]],
        ("Middle East",  "South Asia"):    [["port254"],                []],
        ("Middle East",  "SE Asia"):       [["port254", "port1201"],    ["port1201"]],
        ("Middle East",  "East Asia"):     [["port1201"],               ["port474"]],
        ("SE Asia",      "East Asia"):     [["port474"],                ["port1065"],            []],
        ("SE Asia",      "South Asia"):    [["port254"],                ["port1201"],            []],
        ("South Asia",   "East Asia"):     [["port1201"],               ["port254", "port1201"], ["port306", "port1201"]],
        ("South Asia",   "South Asia"):    [[],                         ["port254"],             ["port1201"]],
    }

    # Region assignments
    _REGIONS = {
        "port776":  "South Asia",   "port777":  "South Asia",
        "port235":  "South Asia",   "port1367": "South Asia",
        "port442":  "South Asia",   "port583":  "South Asia",
        "port907":  "South Asia",   "port1188": "East Asia",
        "port1201": "SE Asia",      "port824":  "East Asia",
        "port1189": "East Asia",    "port1065": "East Asia",
        "port474":  "East Asia",    "port1069": "East Asia",
        "port1297": "East Asia",    "port1114": "Europe",
        "port306":  "Middle East",  "port446":  "Europe",
        "port815":  "Americas",     "port664":  "Americas",
        "port1269": "SE Asia",      "port254":  "South Asia",
        "port192":  "Middle East",  "port57":   "Europe",
        "port343":  "Europe",       "port1417": "East Asia",
        "port543":  "South Asia",
    }

    def get_candidate_routes(
        self,
        origin: str,
        destination: str,
        max_routes: int = 5,
    ) -> list[list[str]]:
        """
        Return up to max_routes candidate routes from origin to destination.
        Always includes direct route and hub-via routes based on corridor logic.
        Deduplicates and filters geographically sensible routes only.
        """
        if origin == destination:
            raise ValueError("origin == destination")

        candidates = set()
        origin_region = self._REGIONS.get(origin, "Unknown")
        dest_region   = self._REGIONS.get(destination, "Unknown")

        # 1. Direct route (always included)
        candidates.add(tuple([origin, destination]))

        # 2. Corridor-based hub routes
        key = (origin_region, dest_region)
        rev = (dest_region, origin_region)
        hub_options = self._CORRIDOR_HUBS.get(key) or self._CORRIDOR_HUBS.get(rev) or []

        for hub_seq in hub_options:
            if not hub_seq:
                continue
            # Filter out hubs that ARE the origin or destination
            clean = [h for h in hub_seq if h not in (origin, destination)]
            if clean:
                route = [origin] + clean + [destination]
                candidates.add(tuple(route))

        # 3. Single-hub alternatives from ALL_HUBS for long-haul routes
        direct_dist = _haversine(origin, destination)
        if direct_dist > 4000:
            for hub in ALL_HUBS:
                if hub in (origin, destination):
                    continue
                route = [origin, hub, destination]
                if _is_geographically_sensible(route):
                    candidates.add(tuple(route))

        # 4. Two-hub routes for ultra-long haul (>10000 km)
        if direct_dist > 10000:
            hub_list = list(ALL_HUBS - {origin, destination})
            for i, h1 in enumerate(hub_list):
                for h2 in hub_list[i+1:]:
                    route = [origin, h1, h2, destination]
                    if _is_geographically_sensible(route):
                        candidates.add(tuple(route))

        # Convert, filter sensible, sort by total distance, cap at max_routes
        valid = [
            list(r) for r in candidates
            if _is_geographically_sensible(list(r))
        ]
        valid.sort(key=_route_distance)
        return valid[:max_routes]


# Singleton instance
_route_graph = RouteGraph()


# ─────────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────────

@dataclass
class LegCalibration:
    berth_wait_mu:      float = 1.5
    berth_wait_sigma:   float = 0.6
    handling_mu:        float = 1.8
    handling_sigma:     float = 0.4
    base_delay_mu:      float = 0.0
    base_delay_sigma:   float = 2.0
    disruption_probs:   dict  = field(default_factory=lambda: {
        "none": 0.60, "congestion": 0.15,
        "weather": 0.12, "strike": 0.08, "equipment": 0.05,
    })
    disruption_delay_params: dict = field(default_factory=lambda: {
        "congestion": (2.0, 0.8), "weather": (1.8, 1.0),
        "strike":     (3.0, 0.9), "equipment": (1.5, 0.7),
    })


@dataclass
class SimulationOutput:
    origin:              str
    destination:         str
    route:               list
    cargo_type:          str
    n_runs:              int
    delay_p50:           float
    delay_p75:           float
    delay_p90:           float
    delay_p95:           float
    delay_mean:          float
    delay_std:           float
    delay_min:           float
    delay_max:           float
    prob_any_disruption: float
    prob_missed_sla:     float
    disruption_breakdown: dict
    cascade_risk:        dict
    total_distance_km:   float
    raw_delays:          list = field(default_factory=list)

    def summary(self) -> str:
        route_str = " → ".join(PORTS.get(p, {}).get("name", p) for p in self.route)
        lines = [
            f"  Route  : {route_str}",
            f"  Dist   : {self.total_distance_km:,.0f} km  |  Legs: {len(self.route)-1}",
            f"  P50    : {self.delay_p50:.1f} hrs  |  P90: {self.delay_p90:.1f} hrs  |  P95: {self.delay_p95:.1f} hrs",
            f"  Disrupt: {self.prob_any_disruption*100:.1f}%  |  Missed SLA: {self.prob_missed_sla*100:.1f}%",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw_delays", None)
        return d


@dataclass
class RouteComparisonOutput:
    origin:       str
    destination:  str
    cargo_type:   str
    n_runs:       int
    routes:       list   # list of SimulationOutput sorted by score
    recommended:  SimulationOutput = None

    def summary(self) -> str:
        lines = [
            "=" * 65,
            f"  Route Comparison: {self.origin} → {self.destination}",
            f"  Cargo: {self.cargo_type}  |  Runs per route: {self.n_runs:,}",
            "=" * 65,
        ]
        for i, r in enumerate(self.routes):
            tag = "  ★ RECOMMENDED" if r is self.recommended else ""
            lines.append(f"\n  Option {i+1}{tag}")
            lines.append(r.summary())
        lines.append("=" * 65)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "origin":      self.origin,
            "destination": self.destination,
            "cargo_type":  self.cargo_type,
            "n_runs":      self.n_runs,
            "recommended_route": " → ".join(
                PORTS.get(p, {}).get("name", p)
                for p in (self.recommended.route if self.recommended else [])
            ),
            "routes": [r.to_dict() for r in self.routes],
        }

    def for_llm(self, risk_scores: dict = None) -> dict:
        """Compact dict for LLM prompt — keeps token count low."""
        return {
            "origin":      self.origin,
            "destination": self.destination,
            "cargo_type":  self.cargo_type,
            "recommended": " → ".join(
                PORTS.get(p, {}).get("name", p)
                for p in (self.recommended.route if self.recommended else [])
            ),
            "risk_scores": {
                PORTS.get(k, {}).get("name", k): round(v * 100, 1)
                for k, v in (risk_scores or {}).items()
            },
            "routes": [
                {
                    "route":         " → ".join(PORTS.get(p, {}).get("name", p) for p in r.route),
                    "legs":          len(r.route) - 1,
                    "distance_km":   round(r.total_distance_km),
                    "delay_p50_hrs": r.delay_p50,
                    "delay_p90_hrs": r.delay_p90,
                    "disruption_pct": round(r.prob_any_disruption * 100, 1),
                    "missed_sla_pct": round(r.prob_missed_sla * 100, 1),
                    "top_disruption": max(
                        {k: v for k, v in r.disruption_breakdown.items() if k != "none"},
                        key=r.disruption_breakdown.get,
                        default="none",
                    ),
                }
                for r in self.routes
            ],
        }


# ─────────────────────────────────────────────────────────────────
# CALIBRATOR
# ─────────────────────────────────────────────────────────────────

class Calibrator:

    def __init__(self):
        self.global_leg      = LegCalibration()
        self.by_cargo        = {}
        self.by_season       = {}
        self.by_port         = {}
        self.cascade_matrix  = {}
        self.sla_threshold   = 12.0

    def _fit_lognormal(self, series: pd.Series) -> tuple:
        vals = series[series > 0].dropna()
        if len(vals) < 5:
            return 1.5, 0.6
        try:
            sigma, _, scale = lognorm.fit(vals, floc=0)
            return float(np.log(scale)), float(sigma)
        except Exception:
            return float(np.log(vals.mean() + 1e-6)), float(vals.std() / (vals.mean() + 1e-6))

    def _fit_disruption_probs(self, legs: pd.DataFrame) -> dict:
        counts = legs["disruption_type"].value_counts(normalize=True)
        probs  = {t: float(counts.get(t, 0.0)) for t in DISRUPTION_TYPES}
        total  = sum(probs.values())
        return {k: v / total for k, v in probs.items()} if total > 0 else probs

    def _fit_disruption_delays(self, legs: pd.DataFrame) -> dict:
        defaults = {"congestion":(2.0,0.8),"weather":(1.8,1.0),"strike":(3.0,0.9),"equipment":(1.5,0.7)}
        params   = {}
        for dtype in DISRUPTION_TYPES[1:]:
            sub = legs[(legs["disruption_type"] == dtype) & (legs["disruption_duration_hrs"] > 0)]["disruption_duration_hrs"]
            params[dtype] = tuple(round(x,4) for x in (self._fit_lognormal(sub) if len(sub) >= 5 else defaults[dtype]))
        return params

    def calibrate(self, ships_path: str, legs_path: str) -> None:
        print("Calibrating...")
        ships = pd.read_csv(ships_path)
        legs  = pd.read_csv(legs_path)

        bad = (legs["from_port_id"] == legs["to_port_id"]).sum()
        if bad > 0:
            print(f"  Dropping {bad} same-node legs")
            legs = legs[legs["from_port_id"] != legs["to_port_id"]]

        print(f"  Shipments: {len(ships):,}  |  Legs: {len(legs):,}")
        self.sla_threshold = float(ships["total_delay_hours"].quantile(0.75))

        bw_mu, bw_sig = self._fit_lognormal(legs["berth_wait_hrs"])
        hd_mu, hd_sig = self._fit_lognormal(legs["handling_time_hrs"])
        base           = legs[legs["disruption_occurred"] == 0]["leg_delay_hours"]

        self.global_leg = LegCalibration(
            berth_wait_mu    = round(bw_mu, 4), berth_wait_sigma = round(bw_sig, 4),
            handling_mu      = round(hd_mu, 4), handling_sigma   = round(hd_sig, 4),
            base_delay_mu    = round(float(base.mean()), 4),
            base_delay_sigma = round(float(base.std()),  4),
            disruption_probs          = self._fit_disruption_probs(legs),
            disruption_delay_params   = self._fit_disruption_delays(legs),
        )

        merged = legs.merge(ships[["shipment_id","cargo_type","season"]], on="shipment_id", how="left")

        for cargo in merged["cargo_type"].dropna().unique():
            sub = merged[merged["cargo_type"] == cargo]
            if len(sub) < 20: continue
            bw_mu, bw_sig = self._fit_lognormal(sub["berth_wait_hrs"])
            hd_mu, hd_sig = self._fit_lognormal(sub["handling_time_hrs"])
            self.by_cargo[cargo] = LegCalibration(
                berth_wait_mu=round(bw_mu,4), berth_wait_sigma=round(bw_sig,4),
                handling_mu=round(hd_mu,4),   handling_sigma=round(hd_sig,4),
                base_delay_mu=self.global_leg.base_delay_mu,
                base_delay_sigma=self.global_leg.base_delay_sigma,
                disruption_probs=self._fit_disruption_probs(sub),
                disruption_delay_params=self._fit_disruption_delays(sub),
            )

        for season in ["monsoon","winter","summer"]:
            sub = merged[merged["season"] == season]
            if len(sub) >= 10:
                self.by_season[season] = self._fit_disruption_probs(sub)

        for port_id in legs["from_port_id"].unique():
            sub = legs[legs["from_port_id"] == port_id]
            if len(sub) < 10: continue
            bw_mu, bw_sig = self._fit_lognormal(sub["berth_wait_hrs"])
            hd_mu, hd_sig = self._fit_lognormal(sub["handling_time_hrs"])
            self.by_port[port_id] = {
                "berth_wait_mu": round(bw_mu,4), "berth_wait_sigma": round(bw_sig,4),
                "handling_mu":   round(hd_mu,4), "handling_sigma":   round(hd_sig,4),
            }

        for _, row in ships.iterrows():
            o     = row["origin_port_id"]
            d     = row["destination_port_id"]
            inter = str(row.get("intermediate_ports","") or "")
            if o not in self.cascade_matrix:
                self.cascade_matrix[o] = {}
            name_to_id = {v["name"]: k for k, v in PORTS.items()}
            downstream = [d] + [name_to_id[n.strip()] for n in inter.split("|") if n.strip() in name_to_id]
            for dp in downstream:
                if dp != o:
                    self.cascade_matrix[o][dp] = self.cascade_matrix[o].get(dp, 0) + 1

        for o in self.cascade_matrix:
            total = sum(self.cascade_matrix[o].values())
            if total > 0:
                self.cascade_matrix[o] = {k: round(v/total,4) for k,v in self.cascade_matrix[o].items()}

        print(f"  SLA threshold: {self.sla_threshold:.1f} hrs")
        print(f"  Cargo types: {list(self.by_cargo.keys())}")
        print(f"  Ports calibrated: {len(self.by_port)}")
        print("  Done.\n")

    def get_leg_calibration(self, cargo_type: str) -> LegCalibration:
        return self.by_cargo.get(cargo_type, self.global_leg)

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({
                "global_leg":     asdict(self.global_leg),
                "by_cargo":       {k: asdict(v) for k,v in self.by_cargo.items()},
                "by_season":      self.by_season,
                "by_port":        self.by_port,
                "cascade_matrix": self.cascade_matrix,
                "sla_threshold":  self.sla_threshold,
            }, f, indent=2)
        print(f"Calibration saved: {path}")

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.global_leg     = LegCalibration(**data["global_leg"])
        self.by_cargo       = {k: LegCalibration(**v) for k,v in data["by_cargo"].items()}
        self.by_season      = data["by_season"]
        self.by_port        = data["by_port"]
        self.cascade_matrix = data["cascade_matrix"]
        self.sla_threshold  = data["sla_threshold"]
        print(f"Calibration loaded: {path}")


# ─────────────────────────────────────────────────────────────────
# SIMPY LEG PROCESS
# ─────────────────────────────────────────────────────────────────

def _run_leg(env, from_id, to_id, cargo_type, calib, port_calib,
             risk_score, season, season_probs, rng, leg_results, disruptions):

    dist     = _haversine(from_id, to_id)
    speed    = CARGO_SPEEDS.get(cargo_type, 16.0) * float(rng.normal(1.0, 0.05))
    transit  = dist / max(speed, 5.0)

    pc      = port_calib.get(from_id, {})
    bw_mu   = pc.get("berth_wait_mu",    calib.berth_wait_mu)
    bw_sig  = pc.get("berth_wait_sigma", calib.berth_wait_sigma)
    hd_mu   = pc.get("handling_mu",      calib.handling_mu)
    hd_sig  = pc.get("handling_sigma",   calib.handling_sigma)

    berth     = float(np.clip(rng.lognormal(bw_mu, bw_sig), 0.2, 48.0))
    handling  = float(np.clip(rng.lognormal(hd_mu, hd_sig), 0.5, 24.0))
    scheduled = transit + berth + handling

    yield env.timeout(scheduled)

    base_delay = float(max(0.0, rng.normal(calib.base_delay_mu, calib.base_delay_sigma)))

    d_probs = dict(calib.disruption_probs)
    if season_probs:
        for k in d_probs:
            d_probs[k] = 0.6 * d_probs[k] + 0.4 * season_probs.get(k, d_probs[k])

    non_none = sum(v for k,v in d_probs.items() if k != "none")
    boost    = risk_score * non_none
    d_probs["none"] = max(0.05, d_probs["none"] - boost)
    leftover = 1.0 - d_probs["none"]
    if non_none > 0:
        scale = leftover / non_none
        for k in d_probs:
            if k != "none":
                d_probs[k] *= scale
    total = sum(d_probs.values())
    d_probs = {k: v/total for k,v in d_probs.items()}

    chosen        = rng.choice(list(d_probs.keys()), p=list(d_probs.values()))
    disrupt_delay = 0.0

    if chosen != "none":
        mu, sigma = calib.disruption_delay_params.get(chosen, (2.0, 0.8))
        disrupt_delay = float(np.clip(rng.lognormal(mu, sigma), 0.1, 96.0))
        yield env.timeout(disrupt_delay)
        disruptions.append({"from_port": from_id, "to_port": to_id,
                             "type": chosen, "delay_hrs": round(disrupt_delay, 3)})

    leg_results.append({
        "from_port":     from_id,
        "to_port":       to_id,
        "dist_km":       round(dist, 2),
        "scheduled_hrs": round(scheduled, 4),
        "actual_hrs":    round(scheduled + base_delay + disrupt_delay, 4),
        "delay_hrs":     round(base_delay + disrupt_delay, 4),
        "disruption":    chosen,
    })


# ─────────────────────────────────────────────────────────────────
# SIMULATION MODEL
# ─────────────────────────────────────────────────────────────────

class SimulationModel:

    def __init__(self):
        self.calibrator   = Calibrator()
        self.route_graph  = _route_graph
        self._calibrated  = False

    def calibrate(self, ships_path: str, legs_path: str) -> None:
        self.calibrator.calibrate(ships_path, legs_path)
        self._calibrated = True

    def save_calibration(self, path: str = "calibration.json") -> None:
        self.calibrator.save(path)

    def load_calibration(self, path: str = "calibration.json") -> None:
        self.calibrator.load(path)
        self._calibrated = True

    def _simulate_route(
        self,
        route:       list,
        cargo_type:  str,
        risk_scores: dict,
        season:      str,
        n_runs:      int,
        seed:        int,
    ) -> SimulationOutput:
        """Monte Carlo simulate a specific route (list of portids)."""
        if not self._calibrated:
            raise RuntimeError("Call calibrate() or load_calibration() first.")

        calib        = self.calibrator.get_leg_calibration(cargo_type)
        season_probs = self.calibrator.by_season.get(season, {})
        port_calib   = self.calibrator.by_port
        rng_master   = np.random.default_rng(seed)

        all_delays, all_missed, all_cascade = [], [], []
        disrupt_counts = {t: 0 for t in DISRUPTION_TYPES}

        for _ in range(n_runs):
            child_rng   = np.random.default_rng(rng_master.integers(0, 2**32))
            env         = simpy.Environment()
            leg_results = []
            disruptions = []

            def process(env):
                for from_id, to_id in zip(route[:-1], route[1:]):
                    risk = risk_scores.get(from_id, 0.0)
                    yield env.process(_run_leg(
                        env, from_id, to_id, cargo_type,
                        calib, port_calib, risk,
                        season, season_probs, child_rng,
                        leg_results, disruptions,
                    ))
                    if to_id != route[-1]:
                        yield env.timeout(float(child_rng.uniform(1.5, 4.0)))

            env.process(process(env))
            env.run()

            total_delay = sum(r["delay_hrs"] for r in leg_results)
            all_delays.append(total_delay)
            all_missed.append(total_delay > self.calibrator.sla_threshold)

            for d in disruptions:
                disrupt_counts[d["type"]] = disrupt_counts.get(d["type"], 0) + 1

            # Cascade
            origin     = route[0]
            cascade_map = self.calibrator.cascade_matrix.get(origin, {})
            for port_id, freq in cascade_map.items():
                if port_id not in route and child_rng.random() < freq * 0.4:
                    all_cascade.append(port_id)

        delays = np.array(all_delays)
        cascade_risk = {
            pid: round(all_cascade.count(pid) / n_runs, 4)
            for pid in set(all_cascade)
        }
        disrupt_breakdown = {k: round(v / n_runs, 4) for k, v in disrupt_counts.items()}

        origin_name = PORTS.get(route[0],  {}).get("name", route[0])
        dest_name   = PORTS.get(route[-1], {}).get("name", route[-1])

        return SimulationOutput(
            origin              = origin_name,
            destination         = dest_name,
            route               = route,
            cargo_type          = cargo_type,
            n_runs              = n_runs,
            delay_p50           = round(float(np.percentile(delays, 50)), 2),
            delay_p75           = round(float(np.percentile(delays, 75)), 2),
            delay_p90           = round(float(np.percentile(delays, 90)), 2),
            delay_p95           = round(float(np.percentile(delays, 95)), 2),
            delay_mean          = round(float(delays.mean()), 2),
            delay_std           = round(float(delays.std()),  2),
            delay_min           = round(float(delays.min()),  2),
            delay_max           = round(float(delays.max()),  2),
            prob_any_disruption = round(sum(v for k,v in disrupt_counts.items() if k!="none") / n_runs, 4),
            prob_missed_sla     = round(sum(all_missed) / n_runs, 4),
            disruption_breakdown = disrupt_breakdown,
            cascade_risk        = cascade_risk,
            total_distance_km   = round(_route_distance(route), 1),
            raw_delays          = [round(d, 2) for d in delays.tolist()],
        )

    def run(
        self,
        origin_port_id:      str,
        destination_port_id: str,
        cargo_type:          str   = "container",
        cargo_volume_teu:    float = 300.0,
        risk_scores:         Optional[dict] = None,
        season:              str   = "summer",
        n_runs:              int   = 1000,
        seed:                int   = 42,
    ) -> SimulationOutput:
        """Simulate the best single route (shortest path with hub logic)."""
        if origin_port_id not in PORTS:
            raise ValueError(f"Unknown port: {origin_port_id}")
        if destination_port_id not in PORTS:
            raise ValueError(f"Unknown port: {destination_port_id}")
        if origin_port_id == destination_port_id:
            raise ValueError("origin and destination must differ")

        risk_scores = risk_scores or {}
        rng         = np.random.default_rng(seed)

        # Use route graph to get best single route
        candidates = self.route_graph.get_candidate_routes(origin_port_id, destination_port_id, max_routes=3)
        route      = candidates[0]   # shortest sensible route

        origin_name = PORTS[origin_port_id]["name"]
        dest_name   = PORTS[destination_port_id]["name"]
        print(f"Simulating {origin_name} → {dest_name}  [{cargo_type}]  "
              f"Route: {' → '.join(PORTS.get(p,{}).get('name',p) for p in route)}")

        return self._simulate_route(route, cargo_type, risk_scores, season, n_runs, seed)

    def compare_routes(
        self,
        origin_port_id:      str,
        destination_port_id: str,
        cargo_type:          str   = "container",
        cargo_volume_teu:    float = 300.0,
        risk_scores:         Optional[dict] = None,
        season:              str   = "summer",
        n_runs:              int   = 500,
        max_routes:          int   = 5,
        seed:                int   = 42,
    ) -> RouteComparisonOutput:
        """
        Simulate all candidate routes and rank them.

        Ranking score = weighted combination of:
          - P50 delay (40%)
          - P90 delay (30%)  — tail risk matters
          - disruption probability (20%)
          - missed SLA probability (10%)

        Lower score = better route.
        """
        if origin_port_id not in PORTS:
            raise ValueError(f"Unknown port: {origin_port_id}")
        if destination_port_id not in PORTS:
            raise ValueError(f"Unknown port: {destination_port_id}")
        if origin_port_id == destination_port_id:
            raise ValueError("origin and destination must differ")

        risk_scores = risk_scores or {}
        rng         = np.random.default_rng(seed)

        candidates = self.route_graph.get_candidate_routes(
            origin_port_id, destination_port_id, max_routes=max_routes
        )

        origin_name = PORTS[origin_port_id]["name"]
        dest_name   = PORTS[destination_port_id]["name"]

        print(f"\nComparing {len(candidates)} routes: {origin_name} → {dest_name}  [{cargo_type}]")
        print(f"Runs per route: {n_runs:,}\n")

        results = []
        for i, route in enumerate(candidates):
            route_str = " → ".join(PORTS.get(p, {}).get("name", p) for p in route)
            print(f"  [{i+1}/{len(candidates)}] {route_str}")
            child_seed = int(rng.integers(0, 2**32))
            result     = self._simulate_route(
                route, cargo_type, risk_scores, season, n_runs, child_seed
            )
            results.append(result)

        # Normalize metrics 0-1 for scoring
        def _norm(vals):
            mn, mx = min(vals), max(vals)
            if mx == mn: return [0.5] * len(vals)
            return [(v - mn) / (mx - mn) for v in vals]

        p50s    = _norm([r.delay_p50           for r in results])
        p90s    = _norm([r.delay_p90           for r in results])
        dispts  = _norm([r.prob_any_disruption for r in results])
        slas    = _norm([r.prob_missed_sla     for r in results])

        scores  = [
            0.40 * p50 + 0.30 * p90 + 0.20 * dis + 0.10 * sla
            for p50, p90, dis, sla in zip(p50s, p90s, dispts, slas)
        ]

        ranked = sorted(zip(scores, results), key=lambda x: x[0])
        ranked_results = [r for _, r in ranked]

        comparison = RouteComparisonOutput(
            origin      = origin_name,
            destination = dest_name,
            cargo_type  = cargo_type,
            n_runs      = n_runs,
            routes      = ranked_results,
            recommended = ranked_results[0],
        )

        print(comparison.summary())
        return comparison

    def run_batch(self, shipments: list, n_runs: int = 500, seed: int = 42) -> pd.DataFrame:
        rows = []
        rng  = np.random.default_rng(seed)
        for i, s in enumerate(shipments):
            try:
                out = self.run(
                    origin_port_id      = s["origin_port_id"],
                    destination_port_id = s["destination_port_id"],
                    cargo_type          = s.get("cargo_type", "container"),
                    risk_scores         = s.get("risk_scores", {}),
                    season              = s.get("season", "summer"),
                    n_runs              = n_runs,
                    seed                = int(rng.integers(0, 2**32)),
                )
                row = out.to_dict()
                row["shipment_idx"] = i
                rows.append(row)
            except Exception as e:
                print(f"  [!] Shipment {i} failed: {e}")
        return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────
# LLM FORMATTER  — updated to handle both single + comparison
# ─────────────────────────────────────────────────────────────────

def format_for_llm(
    output,   # SimulationOutput or RouteComparisonOutput
    company_context: dict = None,
) -> dict:
    ctx = company_context or {}

    if isinstance(output, RouteComparisonOutput):
        payload = output.for_llm()
        best    = output.recommended
    else:
        best    = output
        payload = {
            "route":       f"{output.origin} → {output.destination}",
            "cargo_type":  output.cargo_type,
            "routes":      [{
                "route":          f"{output.origin} → {output.destination}",
                "legs":           len(output.route) - 1,
                "distance_km":    round(output.total_distance_km),
                "delay_p50_hrs":  output.delay_p50,
                "delay_p90_hrs":  output.delay_p90,
                "disruption_pct": round(output.prob_any_disruption * 100, 1),
                "missed_sla_pct": round(output.prob_missed_sla * 100, 1),
            }],
        }

    if ctx:
        delay         = best.delay_p50
        p90_delay     = best.delay_p90
        fuel_rate     = ctx.get("fuel_rate",          90.0)
        sla_penalty   = ctx.get("sla_penalty_per_hr", 500.0)
        cargo_value   = ctx.get("cargo_value_usd",    500000.0)
        insurance     = ctx.get("insurance_coverage", 0.8)
        discount      = ctx.get("deal_discount_pct",  0.0)
        base_cost     = delay * fuel_rate
        sla_cost      = p90_delay * sla_penalty if best.prob_missed_sla > 0.2 else 0.0
        risk_cost     = cargo_value * best.prob_any_disruption * (1 - insurance)
        total         = (base_cost + sla_cost + risk_cost) * (1 - discount / 100)
        payload["cost_estimate_usd"] = {
            "base_delay_cost":  round(base_cost, 2),
            "sla_penalty_risk": round(sla_cost, 2),
            "cargo_risk_cost":  round(risk_cost, 2),
            "total_estimated":  round(total, 2),
        }

    return payload


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, os

    parser = argparse.ArgumentParser()
    parser.add_argument("--ships",   default="shipments.csv")
    parser.add_argument("--legs",    default="legs.csv")
    parser.add_argument("--calib",   default="calibration.json")
    parser.add_argument("--runs",    type=int,   default=500)
    parser.add_argument("--origin",  default="port815")   # New York
    parser.add_argument("--dest",    default="port442")   # Kolkata
    parser.add_argument("--cargo",   default="container")
    parser.add_argument("--season",  default="summer")
    parser.add_argument("--risk",    type=float, default=0.65)
    parser.add_argument("--compare", action="store_true", help="Compare all candidate routes")
    parser.add_argument("--recalib", action="store_true")
    args = parser.parse_args()

    sim = SimulationModel()
    if args.recalib or not os.path.exists(args.calib):
        sim.calibrate(args.ships, args.legs)
        sim.save_calibration(args.calib)
    else:
        sim.load_calibration(args.calib)

    risk_scores = {args.origin: args.risk}

    if args.compare:
        result = sim.compare_routes(
            origin_port_id      = args.origin,
            destination_port_id = args.dest,
            cargo_type          = args.cargo,
            season              = args.season,
            risk_scores         = risk_scores,
            n_runs              = args.runs,
        )
    else:
        result = sim.run(
            origin_port_id      = args.origin,
            destination_port_id = args.dest,
            cargo_type          = args.cargo,
            season              = args.season,
            risk_scores         = risk_scores,
            n_runs              = args.runs,
        )

    llm_payload = format_for_llm(result, company_context={
        "fuel_rate": 95.0, "sla_penalty_per_hr": 600.0,
        "cargo_value_usd": 750000.0, "insurance_coverage": 0.75,
        "deal_discount_pct": 5.0,
    })
    print("\n── LLM Payload ──────────────────────────────────────")
    print(json.dumps(llm_payload, indent=2))