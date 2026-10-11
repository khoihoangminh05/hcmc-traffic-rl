"""Subprocess vectorized MicroAlleyEnv — true CPU parallelism for rollouts."""

from __future__ import annotations

import multiprocessing as mp
from typing import Any

import numpy as np

from .mappo_micro_env import MicroAlleyEnv


def _pack_obs(
    obs: dict[str, np.ndarray], info: dict[str, Any], agents: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    o = np.stack([obs[a] for a in agents], axis=0).astype(np.float32)
    m = np.stack([info["masks"][a] for a in agents], axis=0).astype(np.float32)
    return o, m


def _worker(remote: Any, parent_remote: Any, env_kwargs: dict[str, Any]) -> None:
    parent_remote.close()
    env = MicroAlleyEnv(**env_kwargs)
    env.warmup_peak_caches()
    agents = list(env.agents)
    try:
        while True:
            cmd, data = remote.recv()
            if cmd == "set_od_pool":
                env.set_od_pool(data)
                remote.send(True)
            elif cmd == "reset":
                seed, t = data
                obs, gstate, info = env.reset(seed=int(seed), options={"t": float(t)})
                o, m = _pack_obs(obs, info, agents)
                remote.send((o, np.asarray(gstate, dtype=np.float32), m))
            elif cmd == "step":
                acts_arr = np.asarray(data, dtype=np.int64)  # [n_agents]
                actions = {a: int(acts_arr[i]) for i, a in enumerate(agents)}
                obs, rewards, _, _, gstate, info = env.step(actions)
                o, m = _pack_obs(obs, info, agents)
                r = float(np.mean([rewards[a] for a in agents]))
                done = bool(info["all_done"])
                # zero placeholder when not done — cuts meaningful traffic mid-episode
                travels = (
                    np.asarray(env._travel, dtype=np.float64)
                    if done
                    else np.zeros(len(agents), dtype=np.float64)
                )
                remote.send((o, np.asarray(gstate, dtype=np.float32), m, r, done, travels))
            elif cmd == "close":
                remote.close()
                break
            else:
                raise RuntimeError(f"unknown cmd {cmd}")
    except KeyboardInterrupt:
        pass
    finally:
        try:
            remote.close()
        except Exception:
            pass


class SubprocMicroEnvs:
    """n parallel MicroAlleyEnv workers (one process each)."""

    def __init__(self, env_kwargs_list: list[dict[str, Any]], *, start_method: str | None = None) -> None:
        if not env_kwargs_list:
            raise ValueError("need >=1 env")
        methods = mp.get_all_start_methods()
        if start_method is None:
            start_method = "forkserver" if "forkserver" in methods else "spawn"
        ctx = mp.get_context(start_method)
        self.n = len(env_kwargs_list)
        self._remotes: list[Any] = []
        self._procs: list[Any] = []
        for kw in env_kwargs_list:
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_worker, args=(child, parent, kw), daemon=True)
            proc.start()
            child.close()
            self._remotes.append(parent)
            self._procs.append(proc)
        # probe dims
        self._remotes[0].send(("reset", (0, 28800.0)))
        o, g, m = self._remotes[0].recv()
        self.n_agents = int(o.shape[0])
        self.obs_dim = int(o.shape[1])
        self.n_actions = int(m.shape[1])
        self.global_dim = int(g.shape[0])

    def set_od_pool(self, pairs: list[tuple[str, str]]) -> None:
        for r in self._remotes:
            r.send(("set_od_pool", pairs))
        for r in self._remotes:
            r.recv()

    def reset_batch(
        self, seeds: list[int], ts: list[float]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert len(seeds) == self.n and len(ts) == self.n
        for r, s, t in zip(self._remotes, seeds, ts):
            r.send(("reset", (int(s), float(t))))
        outs = [r.recv() for r in self._remotes]
        obs = np.stack([o[0] for o in outs], axis=0)  # [E,A,D]
        g = np.stack([o[1] for o in outs], axis=0)  # [E,G]
        m = np.stack([o[2] for o in outs], axis=0)  # [E,A,Act]
        return obs, g, m

    def step_batch(
        self, actions: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """actions: [E, A] int."""
        assert actions.shape[0] == self.n
        for r, acts in zip(self._remotes, actions):
            r.send(("step", acts))
        outs = [r.recv() for r in self._remotes]
        obs = np.stack([o[0] for o in outs], axis=0)
        g = np.stack([o[1] for o in outs], axis=0)
        m = np.stack([o[2] for o in outs], axis=0)
        rewards = np.asarray([o[3] for o in outs], dtype=np.float64)
        dones = np.asarray([o[4] for o in outs], dtype=np.bool_)
        travels = np.stack([o[5] for o in outs], axis=0)
        return obs, g, m, rewards, dones, travels

    def close(self) -> None:
        for r in self._remotes:
            try:
                r.send(("close", None))
            except Exception:
                pass
        for p in self._procs:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
