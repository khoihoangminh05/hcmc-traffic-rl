"""Subprocess vectorized MicroAlleyEnv — true CPU parallelism for rollouts."""

from __future__ import annotations

import multiprocessing as mp
import traceback
from pathlib import Path
from typing import Any

import numpy as np

from .mappo_micro_env import MicroAlleyEnv


def _pack_obs(
    obs: dict[str, np.ndarray], info: dict[str, Any], agents: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    o = np.stack([obs[a] for a in agents], axis=0).astype(np.float32)
    m = np.stack([info["masks"][a] for a in agents], axis=0).astype(np.float32)
    return o, m


def _sanitize_env_kwargs(kw: dict[str, Any]) -> dict[str, Any]:
    """Paths → str so spawn/forkserver pickling is reliable."""
    out = dict(kw)
    for k in ("density_path", "graph_path"):
        if k in out and out[k] is not None:
            out[k] = str(out[k])
    cat = out.get("density_catalog")
    if isinstance(cat, dict):
        out["density_catalog"] = {str(name): str(p) for name, p in cat.items()}
    return out


def _worker(remote: Any, parent_remote: Any, env_kwargs: dict[str, Any]) -> None:
    parent_remote.close()
    try:
        kw = _sanitize_env_kwargs(env_kwargs)
        # Path() again inside worker
        if kw.get("density_path") is not None:
            kw["density_path"] = Path(kw["density_path"])
        if kw.get("graph_path") is not None:
            kw["graph_path"] = Path(kw["graph_path"])
        if kw.get("density_catalog"):
            kw["density_catalog"] = {
                n: Path(p) for n, p in kw["density_catalog"].items()
            }
        env = MicroAlleyEnv(**kw)
        env.warmup_peak_caches()
        agents = list(env.agents)
        remote.send(("ready", None))
    except Exception as exc:
        remote.send(("error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
        remote.close()
        return

    try:
        while True:
            try:
                cmd, data = remote.recv()
            except EOFError:
                break
            if cmd == "set_od_pool":
                env.set_od_pool(data)
                remote.send(("ok", True))
            elif cmd == "reset":
                seed, t = data
                obs, gstate, info = env.reset(seed=int(seed), options={"t": float(t)})
                o, m = _pack_obs(obs, info, agents)
                remote.send(("ok", (o, np.asarray(gstate, dtype=np.float32), m)))
            elif cmd == "step":
                acts_arr = np.asarray(data, dtype=np.int64)
                actions = {a: int(acts_arr[i]) for i, a in enumerate(agents)}
                obs, rewards, _, _, gstate, info = env.step(actions)
                o, m = _pack_obs(obs, info, agents)
                r = np.asarray([float(rewards[a]) for a in agents], dtype=np.float32)
                done = bool(info["all_done"])
                agent_done = np.asarray(info["agent_done"], dtype=np.bool_)
                travels = (
                    np.asarray(env._travel, dtype=np.float64)
                    if done
                    else np.zeros(len(agents), dtype=np.float64)
                )
                remote.send(
                    (
                        "ok",
                        (
                            o,
                            np.asarray(gstate, dtype=np.float32),
                            m,
                            r,
                            done,
                            travels,
                            agent_done,
                        ),
                    )
                )
            elif cmd == "close":
                remote.send(("ok", None))
                break
            else:
                remote.send(("error", f"unknown cmd {cmd}"))
                break
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        try:
            remote.send(("error", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
        except Exception:
            pass
    finally:
        try:
            remote.close()
        except Exception:
            pass


def _recv_ok(remote: Any, *, what: str) -> Any:
    status, payload = remote.recv()
    if status == "error":
        raise RuntimeError(f"subproc worker failed during {what}:\n{payload}")
    if status not in ("ok", "ready"):
        raise RuntimeError(f"subproc bad status {status!r} during {what}")
    return payload


class SubprocMicroEnvs:
    """n parallel MicroAlleyEnv workers (one process each)."""

    def __init__(
        self, env_kwargs_list: list[dict[str, Any]], *, start_method: str | None = None
    ) -> None:
        if not env_kwargs_list:
            raise ValueError("need >=1 env")
        methods = mp.get_all_start_methods()
        if start_method is None:
            # Prefer forkserver on Linux; fall back to spawn.
            start_method = "forkserver" if "forkserver" in methods else "spawn"
        ctx = mp.get_context(start_method)
        self.n = len(env_kwargs_list)
        self._start_method = start_method
        self._remotes: list[Any] = []
        self._procs: list[Any] = []
        safe_kwargs = [_sanitize_env_kwargs(kw) for kw in env_kwargs_list]
        for kw in safe_kwargs:
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_worker, args=(child, parent, kw), daemon=True)
            proc.start()
            child.close()
            self._remotes.append(parent)
            self._procs.append(proc)
        # Wait for every worker to finish env init (surfaces OOM/import errors clearly).
        for i, r in enumerate(self._remotes):
            try:
                _recv_ok(r, what=f"init worker[{i}]")
            except Exception:
                self.close()
                raise
        # probe dims
        self._remotes[0].send(("reset", (0, 28800.0)))
        o, g, m = _recv_ok(self._remotes[0], what="probe reset")
        self.n_agents = int(o.shape[0])
        self.obs_dim = int(o.shape[1])
        self.n_actions = int(m.shape[1])
        self.global_dim = int(g.shape[0])
        print(
            f"[subproc] start_method={start_method} n={self.n} "
            f"obs={self.obs_dim} global={self.global_dim}",
            flush=True,
        )

    def set_od_pool(self, pairs: list[tuple[str, str]]) -> None:
        for r in self._remotes:
            r.send(("set_od_pool", pairs))
        for i, r in enumerate(self._remotes):
            _recv_ok(r, what=f"set_od_pool[{i}]")

    def reset_batch(
        self, seeds: list[int], ts: list[float]
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        assert len(seeds) == self.n and len(ts) == self.n
        for r, s, t in zip(self._remotes, seeds, ts):
            r.send(("reset", (int(s), float(t))))
        outs = [_recv_ok(r, what="reset") for r in self._remotes]
        obs = np.stack([o[0] for o in outs], axis=0)
        g = np.stack([o[1] for o in outs], axis=0)
        m = np.stack([o[2] for o in outs], axis=0)
        return obs, g, m

    def step_batch(
        self, actions: np.ndarray
    ) -> tuple[
        np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray
    ]:
        """Returns obs, global, masks, rewards, episode_done, travels, agent_done[n, A]."""
        assert actions.shape[0] == self.n
        for r, acts in zip(self._remotes, actions):
            r.send(("step", acts))
        outs = [_recv_ok(r, what="step") for r in self._remotes]
        obs = np.stack([o[0] for o in outs], axis=0)
        g = np.stack([o[1] for o in outs], axis=0)
        m = np.stack([o[2] for o in outs], axis=0)
        rewards = np.stack([o[3] for o in outs], axis=0).astype(np.float32)
        dones = np.asarray([o[4] for o in outs], dtype=np.bool_)
        travels = np.stack([o[5] for o in outs], axis=0)
        agent_done = np.stack([o[6] for o in outs], axis=0).astype(np.bool_)
        return obs, g, m, rewards, dones, travels, agent_done

    def close(self) -> None:
        for r in self._remotes:
            try:
                r.send(("close", None))
            except (BrokenPipeError, EOFError, OSError):
                pass
        for r in self._remotes:
            try:
                r.recv()
            except Exception:
                pass
            try:
                r.close()
            except Exception:
                pass
        for p in self._procs:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
        self._remotes.clear()
        self._procs.clear()
