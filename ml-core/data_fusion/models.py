"""Greenshields fundamental diagram + scalar Kalman filter for edge state."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GreenshieldsParams:
    v_free: float = 12.0  # m/s ~ 43 km/h alley-ish
    k_jam: float = 0.18  # veh/m


def speed_from_density(k: float, params: GreenshieldsParams) -> float:
    k = max(0.0, min(k, params.k_jam * 0.999))
    return params.v_free * (1.0 - k / params.k_jam)


def density_from_speed(v: float, params: GreenshieldsParams) -> float:
    v = max(0.1, min(v, params.v_free))
    return params.k_jam * (1.0 - v / params.v_free)


@dataclass
class Kalman1D:
    """Simple 1D Kalman on density k."""

    x: float = 0.02
    p: float = 1.0
    q: float = 1e-4
    r: float = 5e-3

    def predict(self) -> None:
        self.p = self.p + self.q

    def update(self, z: float) -> float:
        self.predict()
        k_gain = self.p / (self.p + self.r)
        self.x = self.x + k_gain * (z - self.x)
        self.p = (1.0 - k_gain) * self.p
        return self.x
