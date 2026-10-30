# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A research monorepo: a digital twin of the alley ("hẻm") network of District 4 (Quận 4), Ho Chi Minh City, plus multi-agent RL routing on that twin. The paper currently in progress is **MAPPO micro next-hop routing** (`ml-core/marl_agent/mappo_micro_*`). The macro K-path / UAKP / `robust_train` code is legacy.

**Read `.docs/HANDOFF_MAPPO_MICRO.md` before touching MARL code.** It holds the environment spec, the baselines, the version history (v3a→v3v and why each change was made), the clean held-out results, the next tasks, and the research rules below. `.docs/PROGRESS.md` is the living checklist. Most docs are in Vietnamese. The user writes in Vietnamese, so reply in Vietnamese.

## Layout and domain boundaries

| Path | Role | Stack |
|------|------|-------|
| `ingestion-worker/` | Node 1 (local PC): Mapbox travel-time poller + camera crawler → CSV + Redis | NestJS 11, TypeScript, ioredis |
| `ml-core/` | Node 2 (GPU server "sol1"): CV, data fusion, SUMO export, MARL | Python 3.10+, PyTorch, networkx, osmnx |
| `sumo-env/` | SUMO networks, routes, OSM traffic-signal data | SUMO XML |
| `.docs/` | Specs, runbooks, paper outlines, results | Markdown |

Hard rules (from `.docs/CONVENTIONS.md`):
- Never mix languages across domains. Data moves between them only through files, Redis keys, or sync jobs.
- Node 2 code is batch only: explicit input and output paths, a finite set of files, a clear exit code. No `while True` polling loops.
- Node 1 must be resumable: cursors persist the last successful poll or HLS position.
- Commits use Conventional Commits with scopes `ingestion|fusion|cv|marl|sumo|docs|infra`. (Recent history uses plain-sentence subjects; either is accepted.)
- After a block of code works, update `.docs/PROGRESS.md`. If a data contract changes, update `.docs/DATA_CONTRACTS.md` / `ARCHITECTURE.md`.

## Commands

### ml-core (always run from `ml-core/` as modules: `python -m <pkg>.<module>`)

```bash
pip install -r requirements.txt                     # CUDA torch installed separately
ruff check . && black .                             # line length 100, py310 (pyproject.toml)

# Tests are plain scripts (each test is a function called from main()); success prints *_TESTS_OK
python -u -m marl_agent.test_mappo_micro_env        # → MAPPO_MICRO_ENV_TESTS_OK
python -u -m marl_agent.test_mappo_env
python -u -m marl_agent.test_uakp_env
# Run a single test:
python -c "from marl_agent.test_mappo_micro_env import test_live_occupancy_in_obs as t; t()"

# Trainer smoke run (CPU)
python -u -m marl_agent.mappo_micro_train --config marl_agent/configs/quan4_mappo_micro.yaml --device cpu --smoke
# Full training (on sol1, about 20 h). Flags: --seed N --share-coef X --no-alley-info --ippo --max-updates --n-agents
CUDA_VISIBLE_DEVICES=1 python -u -m marl_agent.mappo_micro_train --config marl_agent/configs/quan4_mappo_micro.yaml --device cuda --seed 42

# Official evaluation (clean seeds 60000+; never overwrites older heldout_eval*.json)
python -u -m marl_agent.eval_heldout --run <run_dir> --episodes 30 [--n-agents 100] [--share-coef 8]
# Diagnose a real checkpoint before changing anything
python -u -m marl_agent.diagnose_policy --run <run_dir> --episodes 4

# End-to-end offline smoke (CV stub → fusion → SUMO export → MARL)
python run_smoke_pipeline.py
# Twin building (Paper A side)
python -m data_fusion.build_quan4_map               # OSM → alley graph
python -m data_fusion.sample_od_seeds --n 120       # OD seeds for Mapbox polling
python -m data_fusion.run_quan4_density --l1-peaks ...   # see .docs/QUAN4_DENSITY.md
```

### ingestion-worker

```bash
docker compose up -d redis                          # from repo root; OSRM: --profile routing
npm install && npm run start:dev                    # needs .env (copy .env.example)
npm run lint && npm run format && npm run build     # no unit tests (npm test is a stub)
```

## Data pipeline (big picture)

1. `data_fusion.build_quan4_map` / `build_alleys_from_osm` turn OSM data into an alley graph with stable `alley_id`s (`artifacts/out/quan4/alley_graph.json`). `export_wcc_subgraph` writes the weakly connected subgraph used for training to `artifacts/out/quan4/wcc/` (886 nodes, 1828 directed edges).
2. The ingestion worker polls Mapbox travel times for OD seeds (`ingestion-worker/config/od_pairs.*.json`) and crawls cameras. Cameras do not see inside alleys, so they are a secondary source only.
3. `data_fusion.run_quan4_density` interpolates density `k(t)` for every alley (Greenshields + Kalman). It writes per-peak files `alley_density_*_wcc.json`. `cam_secondary_prior` adds the camera prior, giving the L4 file `alley_density_l4_cam_wcc.json`.
4. `export_sumo` writes `sumo-env/networks/quan4_alleys.net.xml` (with signal tlLogic from `fetch_osm_signals`).
5. MARL reads the WCC graph and density files. Most of `artifacts/out/` is gitignored, including `wcc/` and `marl_runs/`, so these files exist only locally or on sol1.

## MAPPO micro architecture

- `mappo_micro_env.py` (`MicroAlleyEnv`): an **event-clock** simulator, not lock-step. Each `step` is the next decision time. Only vehicles standing at a node act. Edge times use BPR with live occupancy, physical capacity, red-light holds, and one shock event per episode. It also contains every baseline (`dijkstra`, `dijkstra_bpr`, `random`, `greedy_load` = the main baseline, `greedy_informed`, `social`), `run_episode_baseline`, and `evaluate_fair_suite`.
- `mappo_micro_vec.py`: subprocess vector env (16 workers; CPU episode collection is the bottleneck). `mappo_nets.py`: shared actor + central critic (CTDE). `mappo_micro_train.py`: the PPO loop, eval every 50 updates on seeds 50000–50007, early stopping, and `best.pt`.
- Reward is the same for every controller: `−(edge travel time + crowding penalty "city") / 1000`. The comparison objective is mean(travel + city). The potential-based shaping and the decaying revisit/exploration bonus apply **only during MAPPO training**, never to scores or baselines.
- A run dir (`artifacts/out/quan4/marl_runs/<config>_<tag>_<UTC>_seed<N>/`) contains `best.pt`, `ckpt_*.pt`, `metrics.jsonl/csv`, `summary.json`, snapshotted hyperparameters, and `heldout_eval*.json`.
- Git tag `v3v-paper-baseline` freezes the code that produced the reported v3v results. The raw numbers are in `.docs/results_v3v/heldout_raw.txt`.

## Research rules (mandatory, from the handoff)

- **Do not weaken the heuristics.** Any shared rule (applied to every controller) must have its effect on `greedy_load` measured before it is kept.
- **Fairness:** every controller uses the same environment, transitions, reward, and episodes. Only action selection differs.
- **Integrity:** report every run, failed ones included. Never swap out a bad seed silently. Report final numbers only from `eval_heldout` (seeds 60000+), because the end-of-run 30-episode comparison overlaps the `best.pt` selection seeds. Do not change code in the middle of a series of runs.
- **Diagnose before fixing:** measure with `diagnose_policy` on real checkpoints, not on guesses. Treat every training run as the last one: run tests and the smoke run, and check on the real map, before handing over a train command. State how much extra training time each change costs.
- No behaviour cloning (BC) warm start for MAPPO (the user rejected it). The observation exposes only whether a node has a traffic light, never its phase.
- "xem qua" (take a look) = diagnose only, no code edits. "sửa đi" (fix it) = edit.
- Planned direction (not final): move the simulator core to SUMO/libsumo. All controllers then get only information a real system could measure. They may not read the BPR formula, the density files, or `_forecast_entry`. See handoff §12.

## Working with the user and sol1

- The agent cannot SSH into sol1; the user runs commands. Give complete, paste-ready command blocks, never "repeat with X changed". Send long output to a file with `tee` and ask the user to `cat` it, because they cannot copy tmux scrollback. Ask for the tmux session name or `run_dir` alongside any log.
- On sol1: activate conda with `source /mnt/data8tb/minhkhoi/miniconda3/etc/profile.d/conda.sh && conda activate /mnt/data8tb/minhkhoi/hcmc-traffic-rl/conda-env`, then `cd ~/hcmc-traffic-rl/ml-core`. Use `CUDA_VISIBLE_DEVICES=1`. Check `uptime` (load below ~40) before starting parallel runs.
- Pushing directly to `main` is the agreed workflow, so sol1 can `git pull`.
- Do not commit `ml-core/density_l1_index.json`, `.docs/SERVER_SOL1.md`, smoke directories, or probe files.
- The repo lives on a Windows drive and is used from both PowerShell and WSL. Many files can show as modified purely from CRLF/LF differences (equal insertions and deletions). Check `git diff --ignore-cr-at-eol` (or `-w`) before assuming real changes, and do not commit line-ending churn.
