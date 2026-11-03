"""Tests of routing2.objectives. Run: python -u -m routing2.test_objectives

The SUMO test needs SUMO and the v4 net, and is skipped with a message when they are missing.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from .objectives import gain_pct, objective, trip_metrics


def _m(dep, end, arr, rem, ff, cust, tp=0):
    return trip_metrics(dep, end, arr, rem, ff, cust, tp)


def test_both_means_and_index():
    m = _m([0, 0, 0, 0], [100, 200, 300, 400], [1, 1, 1, 1], [0] * 4, [50, 50, 50, 50], [1, 1, 0, 0])
    assert m["T_all_s"] == 250 and m["T_cust_s"] == 150 and m["T_other_s"] == 350
    assert m["congestion_index"] == 5.0
    assert objective(m, 0.5) == 200 and objective(m, 1.0) == 250 and objective(m, 0.0) == 150


def test_unfinished_trips_are_not_dropped():
    """Stuck trips must make the score worse than if they had finished at the end of the run."""
    finished = _m([0, 0], [100, 1000], [1, 1], [0, 0], [100, 100], [1, 1])
    stuck = _m([0, 0], [100, 1000], [1, 0], [0, 80], [100, 100], [1, 1])
    assert stuck["T_all_s"] == finished["T_all_s"] + 40
    assert stuck["unfinished_cust"] == 1 and stuck["arrived_share_all"] == 0.5


def test_never_entered_trip_counts_from_planned_departure():
    m = _m([900], [1000], [0], [120], [120], [0])
    assert m["T_all_s"] == 100 + 120 and m["T_cust_s"] is None
    assert objective(m, 0.5) == m["T_all_s"]


def test_remaining_ignored_once_arrived():
    assert _m([0], [100], [1], [999], [50], [1])["T_all_s"] == 100


def test_all_is_the_trip_weighted_mix():
    m = _m([0, 0, 0], [100, 200, 600], [1, 1, 1], [0] * 3, [10] * 3, [1, 0, 0])
    assert math.isclose(m["T_all_s"], (1 * m["T_cust_s"] + 2 * m["T_other_s"]) / 3)


def test_penetration_one_gives_one_objective():
    m = _m([0, 10], [100, 150], [1, 1], [0, 0], [50, 50], [1, 1])
    assert m["T_all_s"] == m["T_cust_s"] and objective(m, 0.2) == objective(m, 0.9)


def test_gain_sign_and_bad_input():
    a = _m([0], [90], [1], [0], [10], [1])
    b = _m([0], [100], [1], [0], [10], [1])
    assert gain_pct(a, b)["T_all_s"] == 10.0 and gain_pct(a, b)["T_other_s"] is None
    for bad in (lambda: objective(a, 1.5), lambda: _m([0, 1], [1], [1], [0], [1], [1])):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("expected ValueError")


def test_on_sumo():
    """Real net: the fields agree with the old counters, and a cut-off run keeps its unfinished trips."""
    from .demand import make_demand, pick_zones
    from .graph import DEFAULT_GRAPH, load_graph
    from .params import SimConfig
    from .sumo_env import SumoEnvConfig, SumoRoutingEnv, _sumo
    from .sumo_net import build_net

    try:
        _sumo()
        net = build_net(DEFAULT_GRAPH, Path("../sumo-env/networks/v4"))
    except Exception as e:  # noqa: BLE001
        print(f"SKIP test_on_sumo: {e}", flush=True)
        return

    class FF:
        def act(self, req):
            s = req.feat[..., 0] + req.feat[..., 3]
            return s.masked_fill(req.cand < 0, math.inf).argmin(1)

    H = 300.0
    g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=H))
    zones = pick_zones(g, 32, seed=0)
    work = Path("artifacts/out/quan4/routing2_objectives_test")
    d = make_demand(g, zones, [61000], 3000.0, H, 0.5)

    def play(end):
        env = SumoRoutingEnv(g, zones, SumoEnvConfig(net=net, horizon_s=end, work_dir=work))
        return env.run(d, 0, FF(), record=False)

    cut, full = play(H), play(H + 1500.0)
    for ep in (cut, full):
        m = ep.metrics
        assert m["n_all"] == ep.n_trips and m["n_cust"] == ep.n_ctrl
        assert 0 < m["n_cust"] < m["n_all"]
        assert m["unfinished_all"] == ep.n_trips - ep.arrived
        assert m["unfinished_cust"] == ep.n_ctrl - ep.arrived_ctrl
        assert m["congestion_index"] >= 0.9, m
    assert cut.metrics["unfinished_all"] > 0
    # the old counter stops every unfinished trip's clock at the horizon; the new one must not
    assert cut.metrics["T_all_s"] > cut.ttt_s / cut.n_trips
    assert full.metrics["unfinished_all"] == 0, full.metrics
    assert math.isclose(full.metrics["T_all_s"], full.ttt_s / full.n_trips, rel_tol=1e-9)
    # the free-flow remainder should bring the cut-off score close to the fully drained one
    gap = abs(cut.metrics["T_all_s"] - full.metrics["T_all_s"]) / full.metrics["T_all_s"]
    print(f"  cut {cut.metrics['T_all_s']:.1f} old {cut.ttt_s / cut.n_trips:.1f} "
          f"full {full.metrics['T_all_s']:.1f} gap {100 * gap:.1f}% "
          f"T_cust {full.metrics['T_cust_s']:.1f} index {full.metrics['congestion_index']:.3f}", flush=True)


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}", flush=True)
    print("OBJECTIVES_TESTS_OK")


if __name__ == "__main__":
    main()
