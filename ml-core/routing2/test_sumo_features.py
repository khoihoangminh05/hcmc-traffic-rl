"""Tests of the intent and probe features of routing2.sumo_env on the real net.

Run: python -u -m routing2.test_sumo_features
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace
from pathlib import Path

import torch

from .demand import make_demand, pick_zones
from .graph import DEFAULT_GRAPH, load_graph
from .params import SimConfig
from .sumo_env import FEAT_FF, FEAT_INTENT, FEAT_LIVE_TOGO, FEAT_TOGO, FEAT_TT, N_FEAT, SumoEnvConfig, SumoRoutingEnv
from .sumo_net import build_net

H = 240.0
_g = load_graph(DEFAULT_GRAPH, replace(SimConfig(), horizon_s=H))
_z = pick_zones(_g, 32, seed=0)
_net = build_net(DEFAULT_GRAPH, Path("../sumo-env/networks/v4"))
_work = Path("artifacts/out/quan4/routing2_features_test")


def _env(end: float, **kw) -> SumoRoutingEnv:
    return SumoRoutingEnv(_g, _z, SumoEnvConfig(net=_net, horizon_s=end, work_dir=_work, **kw))


class Spy:
    """Free-flow next hop that recounts the intent from SUMO on its own and compares."""

    def __init__(self, env: SumoRoutingEnv):
        self.env, self.chosen, self.rows, self.max_seen, self.nonzero = env, {}, 0, 0, 0

    def act(self, req):
        env = self.env
        sv = env.sumo.vehicle
        live = set(sv.getIDList())
        arrived_or_entered = []
        for vid, e in self.chosen.items():
            if vid in live and sv.getRoadID(vid) == env.eid[e]:
                arrived_or_entered.append(vid)
            elif vid not in live and vid in self.seen_live:
                arrived_or_entered.append(vid)
        for vid in arrived_or_entered:
            del self.chosen[vid]
        self.seen_live |= live
        count = Counter(self.chosen.values())
        s = req.feat[..., FEAT_FF] + req.feat[..., FEAT_TOGO]
        a = s.masked_fill(req.cand < 0, math.inf).argmin(1)
        for i, vid in enumerate(req.vid):
            assert vid.startswith("c"), vid  # background traffic never decides
            for j, c in enumerate(req.cand[i].tolist()):
                if c < 0:
                    continue
                got = int(req.feat[i, j, FEAT_INTENT])
                others = count[c] - (self.chosen.get(vid) == c)
                # the spy may lag SUMO by a step for a vehicle that entered during this one
                assert abs(got - others) <= 2, (vid, c, got, others)
                assert got >= 0
                self.rows += 1
                self.max_seen = max(self.max_seen, got)
                self.nonzero += got > 0
        batch = {}
        for i, vid in enumerate(req.vid):
            batch[vid] = int(req.cand[i, int(a[i])])
        self.chosen.update(batch)
        return a

    seen_live: set = set()


def test_intent_counts_and_never_leaks():
    env = _env(H + 900.0)
    spy = Spy(env)
    spy.seen_live = set()
    d = make_demand(_g, _z, [61000], 6000.0, H, 0.5)
    ep = env.run(d, 0, spy, record=False)
    assert ep.metrics["unfinished_all"] == 0, ep.metrics
    assert spy.nonzero > 0, "intent was never seen, the feature would be useless"
    assert sum(env._intent_n) == 0 and not env._intent, "an arrived vehicle kept its intent"
    assert min(env._intent_n) == 0
    print(f"  intent rows={spy.rows} nonzero={spy.nonzero} max={spy.max_seen}", flush=True)


def test_probe_link_time_is_the_feature():
    class Check:
        def __init__(self, env):
            self.env, self.moved = env, 0

        def act(self, req):
            mask = req.cand >= 0
            c = req.cand.clamp(min=0)
            assert torch.equal(req.feat[..., FEAT_TT][mask], self.env.live_tt[c][mask].float())
            zs = req.dest_zone.unsqueeze(1)
            assert torch.equal(req.feat[..., FEAT_LIVE_TOGO][mask], self.env.live_D[zs, c][mask].float())
            self.moved += int((req.feat[..., FEAT_TT][mask] != req.feat[..., FEAT_FF][mask]).sum())
            return req.live_cost.argmin(1)

    env = _env(H + 300.0, live_every_s=30.0, live_source="probe")
    chk = Check(env)
    env.run(make_demand(_g, _z, [61000], 6000.0, H, 1.0), 0, chk, record=False)
    assert chk.moved > 0, "probe reports never reached the feature"


def test_default_config_keeps_the_old_features():
    class Check:
        def act(self, req):
            mask = req.cand >= 0
            assert torch.equal(req.feat[..., FEAT_LIVE_TOGO][mask], req.feat[..., FEAT_TOGO][mask])
            s = req.feat[..., FEAT_FF] + req.feat[..., FEAT_TOGO]
            return s.masked_fill(~mask, math.inf).argmin(1)

    _env(120.0).run(make_demand(_g, _z, [61000], 2000.0, 120.0, 1.0), 0, Check(), record=False)


def _micro_env(end: float, **kw) -> SumoRoutingEnv:
    return _env(end, micro=True, live_every_s=10.0, live_source="probe", **kw)


def test_micro_serves_one_vehicle_at_a_time_near_the_link_end():
    class Check:
        def __init__(self, env):
            self.env, self.last_t, self.same_step, self.near, self.far, self.seen = env, -1.0, 0, 0, 0, {}

        def act(self, req):
            assert len(req.vid) == 1, "micro must serve single vehicles"
            assert req.t >= self.last_t, "time went backwards"
            self.same_step += req.t == self.last_t
            self.last_t = req.t
            vid = req.vid[0]
            sv, env = self.env.sumo.vehicle, self.env
            if vid in sv.getIDList():
                road = sv.getRoadID(vid)
                e = env.e_of.get(road)
                if e is not None and int(env.dst[e]) == int(req.node[0]):
                    rem = env.sumo.lane.getLength(sv.getLaneID(vid)) - sv.getLanePosition(vid)
                    lim = max(env.cfg.decide_ahead_m, sv.getSpeed(vid) * env.cfg.decide_ahead_s)
                    self.near += rem <= lim + 1e-6
                    self.far += rem > lim + 1e-6
            a = req.live_cost.argmin(1)
            c = int(req.cand[0, int(a[0])])
            self.seen[(req.t, c)] = self.seen.get((req.t, c), 0) + 1
            # a vehicle served after another one at the same time sees that choice
            assert int(req.feat[0, int(a[0]), FEAT_INTENT]) >= self.seen[(req.t, c)] - 1
            return a

    env = _micro_env(H + 900.0)
    chk = Check(env)
    ep = env.run(make_demand(_g, _z, [61000], 6000.0, H, 1.0), 0, chk, record=False)
    assert chk.same_step > 0 and chk.near > 0 and chk.far == 0, (chk.same_step, chk.near, chk.far)
    assert ep.metrics["unfinished_all"] == 0, ep.metrics
    assert sum(env._fleet_n) == 0 and not env._fleet_at and sum(env._intent_n) == 0 and not env._due
    print(f"  decisions={ep.n_decisions} same_time={chk.same_step} missed={ep.missed_decisions} "
          f"teleports={ep.teleports}", flush=True)


def test_micro_count_is_fleet_only():
    class Check:
        def __init__(self, env):
            self.env, self.bigger = env, 0

        def act(self, req):
            ed = self.env.sumo.edge
            for j, c in enumerate(req.cand[0].tolist()):
                if c >= 0:
                    n = int(req.feat[0, j, 2])
                    # within a step of SUMO's count of every vehicle, and never the background too
                    assert n <= ed.getLastStepVehicleNumber(self.env.eid[c]) + 3
                    self.bigger += ed.getLastStepVehicleNumber(self.env.eid[c]) > n
            return req.live_cost.argmin(1)

    env = _micro_env(H)
    chk = Check(env)
    env.run(make_demand(_g, _z, [61000], 6000.0, H, 0.3), 0, chk, record=False)
    assert chk.bigger > 0, "background traffic must be missing from the feature"


def test_events_same_schedule_slow_links_and_restore():
    d = make_demand(_g, _z, [61000], 6000.0, H, 1.0)
    rt = [[int(e)] for e in torch.nonzero(_g.is_alley).squeeze(1)[:200].tolist()]
    kw = dict(incident_rate_per_h=30.0, school_rate_per_h=30.0, incident_seed=5)
    a = _env(H, **kw)._incident_schedule(rt, d.dep_t[0].cpu())
    b = _env(H, **kw)._incident_schedule(rt, d.dep_t[0].cpu())
    assert a == b and any(len(x[1]) > 1 for x in a) and any(len(x[1]) == 1 for x in a)
    assert _env(H)._incident_schedule(rt, d.dep_t[0].cpu()) == []

    class Check:
        def __init__(self, env):
            self.env, self.slow = env, 0

        def act(self, req):
            return req.live_cost.argmin(1)

    env = _micro_env(H + 900.0, **{**kw, "incident_s": 60.0, "school_s": 60.0})
    ep = env.run(d, 0, Check(env), record=False)
    assert ep.incidents > 0 and ep.metrics["unfinished_all"] == 0, ep.metrics


def main() -> None:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}", flush=True)
    print("SUMO_FEATURES_TESTS_OK")


if __name__ == "__main__":
    main()
