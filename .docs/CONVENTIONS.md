# Conventions — HCMC Urban Traffic Optimization

## 1. Domain separation

| Domain | Path | Language |
|--------|------|----------|
| Ingestion (Node 1) | `ingestion-worker/` | TypeScript / NestJS |
| Compute (Node 2) | `ml-core/` | Python 3.10+ |
| Simulation assets | `sumo-env/` | SUMO XML / configs |
| Docs | `.docs/` | Markdown |

- Do **not** place Python packages under `ingestion-worker/` or NestJS modules under `ml-core/`.
- Cross-domain communication is via **files**, **Redis keys**, or **sync jobs** — never direct language interop in-process.

## 2. TypeScript / NestJS (`ingestion-worker/`)

### Tooling (mandatory)

- **ESLint** — NestJS recommended rules + project overrides.
- **Prettier** — single format gate; run before commit.
- Prefer strict TypeScript (`"strict": true` in `tsconfig`).

### Style

- Prefer `async/await` over raw Promise chains for I/O.
- No synchronous blocking FS/network on the hot path.
- Explicit types on public APIs; avoid `any` unless isolated and justified.
- Config via `@nestjs/config` + `.env` (secrets never committed).

### Example shape

```typescript
async function pollTravelTime(odId: string): Promise<TravelTimeSample> {
  const sample = await this.mapboxClient.fetchMatrix(odId);
  await this.redis.lpush(`travel:${odId}`, JSON.stringify(sample));
  await this.csvWriter.append(sample);
  return sample;
}
```

### Scripts (once scaffolded)

```bash
npm run lint
npm run format
npm run build
npm run start:dev
```

## 3. Python (`ml-core/`)

### Tooling (mandatory)

- **Ruff** — lint + import sort.
- **Black** — format (or Ruff format if the team standardizes on one; until then: Black for format, Ruff for lint).
- **Type hints required** on all public functions and module entrypoints (`typing` / `collections.abc`).

### Batch-processing rule

Every CLI / module entrypoint must:

1. Accept explicit `--input` / `--output` (or equivalent) paths.
2. Process a finite set of files.
3. Exit with a clear status code.

**Forbidden on Node 2:**

```python
while True:  # real-time wait for new data — NOT ALLOWED
    ...
```

### Example shape

```python
from pathlib import Path


def run_batch(input_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(input_dir.glob("*.mp4")):
        result = process_video(path)
        (output_dir / f"{path.stem}.json").write_text(result.to_json(), encoding="utf-8")
```

### Suggested local hooks

```bash
ruff check ml-core
black ml-core
# mypy or pyright optional but encouraged for fusion / MARL APIs
```

## 4. Git — Conventional Commits

Format:

```text
<type>(<optional-scope>): <short summary in imperative mood>
```

### Types

| Type | When |
|------|------|
| `feat` | New user-facing capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `chore` | Tooling, deps, scaffolding |
| `refactor` | Internal change, no behavior change |
| `test` | Tests only |
| `perf` | Performance improvement |
| `build` | Docker / CI / compose |
| `ci` | CI config |

### Scopes (preferred)

- `ingestion` — NestJS worker
- `fusion` — data fusion
- `cv` — YOLO / tracker
- `marl` — agents / training
- `sumo` — networks / routes
- `docs` — `.docs/`
- `infra` — docker-compose, Redis, OSRM

### Examples

```text
chore(docs): complete Phase 0 scaffolding checklist
feat(ingestion): add Mapbox matrix poller module
feat(cv): batch YOLOv10 count export
fix(fusion): correct Kalman process noise for alley edges
docs: clarify Local PC to GPU server sync boundary
```

### Rules

- Subject ≤ ~72 characters; no trailing period.
- Body (optional) explains **why**, not only what.
- One logical change per commit when practical.
- Never commit secrets (`.env`, tokens, private keys).

## 5. Documentation updates

After any **working** code block is merged into the tree:

1. Update `.docs/PROGRESS.md` checkboxes.
2. If phase scope changes, sync `.docs/PHASES.md`.
3. If data contracts change, update `.docs/ARCHITECTURE.md`.

## 6. Cursor session workflow

1. Read `.docs/PROGRESS.md`.
2. Propose **1–2** next files; wait for confirmation.
3. Implement only the confirmed scope.
4. Update progress when the block works.
