"""Meso simulator parameters.

Units are motorbikes (HCMC traffic is ~90% motorbikes). The per-class values
are priors, not measurements: P2 calibration fits them to the Mapbox probe
speeds (free speed ~ per-edge p90) and camera counts (capacity). Changing them
changes every controller's environment equally.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClassParams:
    v_free: float  # m/s
    cap: float  # vehicles per second leaving the link
    k_jam: float  # vehicles per metre of link (storage)
    priority: int  # junction priority (SUMO edge priority); a lower-priority approach yields


# Mapbox probes on 2026-10-30: alley speed p50 3.05 / p90 4.43 m/s, other p90 4.72 m/s.
ROAD_CLASS: dict[str, ClassParams] = {
    "alley": ClassParams(v_free=4.5, cap=0.5, k_jam=0.5, priority=1),
    "service": ClassParams(v_free=5.0, cap=0.6, k_jam=0.6, priority=2),
    "residential": ClassParams(v_free=6.0, cap=1.0, k_jam=0.8, priority=3),
    "tertiary": ClassParams(v_free=8.0, cap=2.0, k_jam=1.5, priority=4),
    "secondary": ClassParams(v_free=9.0, cap=3.0, k_jam=2.0, priority=5),
}
DEFAULT_CLASS = "residential"


@dataclass
class SimConfig:
    dt: float = 1.0
    horizon_s: float = 3600.0
    # A vehicle may cross up to this many links per step (links are ~18 m, a few seconds).
    hops_per_step: int = 4
    # Speed on entry falls linearly with occupancy / storage, down to floor * v_free.
    speed_floor: float = 0.15
    min_storage: float = 2.0
    # Gridlock release (SUMO time-to-teleport / MATSim stuckTime): a head vehicle that has
    # waited this long enters its next link even if it is full. Counted as `forced`.
    stuck_time_s: float = 180.0
    signals: bool = True
    signal_cycle_s: float = 60.0
    signal_red_s: float = 30.0
    # P2.3 terms fitted to SUMO (routing2.calib_meso). The defaults switch them off.
    # Driven speed / limit (SUMO motorbikes with sigma 0.5 drive ~5% under the limit).
    speed_factor: float = 1.0
    # Entry speed is not reduced while occupancy / storage <= k_crit (0 = linear from empty).
    k_crit: float = 0.0
    storage_scale: float = 1.0
    cap_scale: float = 1.0
    # Unsignalized junctions: an approach whose priority is below the node's highest
    # incoming priority yields. Its capacity is capped by Siegloch's gap acceptance,
    # exp(-q_major * (tc - tf / 2)) / tf, with q_major the smoothed flow (veh/s) that
    # leaves the node's major approaches. gap_tc_s = 0 switches yielding off.
    gap_tc_s: float = 0.0
    gap_tf_s: float = 2.0
    major_flow_tau_s: float = 30.0


# SimConfig fields that MesoSim accepts per env (calibration runs candidates as envs).
ENV_PARAMS = ("speed_factor", "k_crit", "speed_floor", "storage_scale", "cap_scale", "gap_tc_s", "gap_tf_s")
