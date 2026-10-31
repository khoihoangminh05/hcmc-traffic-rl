import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Cron, CronExpression } from '@nestjs/schedule';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';
import { ProbeCursor, ProbeRoute, ProbeSample, QuotaCursor, TypicalJob } from './mapbox.types';

/**
 * Long-route traffic probes (v4 twin data).
 *
 * The seed poller asks for single 18 m edges on the `driving` profile, which
 * returns Mapbox's speed model, not traffic. A probe is a 0.3–1.5 km route on
 * `driving-traffic` with per-segment speed / congestion annotations, so one
 * request observes every edge along it. Routes come from
 * `ml-core/data_fusion/design_probe_routes.py`: origin, via points on alley
 * edges (sent as non-leg `waypoints` with `bearings`), destination.
 *
 * Two modes, sharing one monthly request counter:
 * - live: one sweep over all routes every MAPBOX_PROBE_INTERVAL_MS during
 *   MAPBOX_PROBE_HOURS → data_raw/mapbox_probe/probe_YYYY-MM-DD.jsonl
 * - typical: POST /mapbox/probe/typical queues every route at every
 *   `depart_at` slot of some future days (Mapbox's historic profile, not a
 *   measurement) → data_raw/mapbox_typical/typical_<startDate>.jsonl
 *
 * Both resume after a restart. Matching to graph edges happens offline on
 * Node 2 (data_fusion.match_probe).
 *
 * Defaults (override via .env):
 * - MAPBOX_PROBE_FILE=                 (empty = probes off)
 * - MAPBOX_PROBE_PROFILE=driving-traffic
 * - MAPBOX_PROBE_INTERVAL_MS=900000    (one full sweep every 15 min)
 * - MAPBOX_PROBE_DELAY_MS=1200         (gap between live HTTP calls)
 * - MAPBOX_TYPICAL_DELAY_MS=300        (gap between typical calls; API limit 300/min)
 * - MAPBOX_PROBE_HOURS=6-20            (Vietnam local hours, start inclusive, end exclusive)
 * - MAPBOX_PROBE_MONTHLY_CAP=95000     (stop before the 100k free tier runs out)
 */
/** 401/403: the token is wrong or revoked. Retrying only burns requests. */
class MapboxAuthError extends Error {}

@Injectable()
export class MapboxProbeService implements OnModuleInit {
  private readonly logger = new Logger(MapboxProbeService.name);
  private liveRunning = false;
  private typicalRunning = false;
  /** Set on 401/403; both modes stay paused until the worker restarts with a new token. */
  private authFailed = false;
  private token = '';
  private routes: ProbeRoute[] = [];
  private quota: QuotaCursor = { monthKey: '', count: 0 };
  private readonly profile: string;
  private readonly intervalMs: number;
  private readonly delayMs: number;
  private readonly typicalDelayMs: number;
  private readonly hourStart: number;
  private readonly hourEnd: number;
  private readonly monthlyCap: number;

  constructor(
    private readonly config: ConfigService,
    private readonly cursors: CursorStore,
    private readonly csv: CsvWriter,
  ) {
    this.profile = this.config.get<string>('MAPBOX_PROBE_PROFILE', 'driving-traffic');
    this.intervalMs = Number(this.config.get<string>('MAPBOX_PROBE_INTERVAL_MS', '900000'));
    this.delayMs = Math.max(500, Number(this.config.get<string>('MAPBOX_PROBE_DELAY_MS', '1200')));
    this.typicalDelayMs = Math.max(
      250,
      Number(this.config.get<string>('MAPBOX_TYPICAL_DELAY_MS', '300')),
    );
    const [h0, h1] = this.config
      .get<string>('MAPBOX_PROBE_HOURS', '6-20')
      .split('-')
      .map((x) => Number(x));
    this.hourStart = Number.isFinite(h0) ? h0 : 6;
    this.hourEnd = Number.isFinite(h1) ? h1 : 20;
    this.monthlyCap = Number(this.config.get<string>('MAPBOX_PROBE_MONTHLY_CAP', '95000'));
  }

  async onModuleInit(): Promise<void> {
    this.token = this.config.get<string>('MAPBOX_ACCESS_TOKEN', '');
    this.routes = await this.loadRoutes();
    const old = await this.readCursor();
    this.quota = await this.cursors.read<QuotaCursor>('mapbox_quota', {
      monthKey: old.monthKey ?? '',
      count: old.monthCount ?? 0,
    });
    if (this.routes.length > 0) {
      this.logger.log(
        `Mapbox probes ready: ${this.routes.length} routes | profile=${this.profile} | ` +
          `hours ${this.hourStart}-${this.hourEnd} VN | sweep≥${this.intervalMs}ms | ` +
          `month ${this.quota.monthKey || '-'} used ${this.quota.count}/${this.monthlyCap}`,
      );
    }
  }

  private async loadRoutes(): Promise<ProbeRoute[]> {
    const file = this.config.get<string>('MAPBOX_PROBE_FILE', '');
    if (!file) return [];
    try {
      const raw = await fs.readFile(path.resolve(file), 'utf8');
      const parsed = JSON.parse(raw) as ProbeRoute[];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      this.logger.warn(
        `MAPBOX_PROBE_FILE unreadable (${err instanceof Error ? err.message : err}); probes off`,
      );
      return [];
    }
  }

  private async sleep(ms: number): Promise<void> {
    await new Promise((r) => setTimeout(r, ms));
  }

  /** Vietnam has no DST: local = UTC + 7. */
  private vnHour(now: Date): number {
    return (now.getUTCHours() + 7) % 24;
  }

  private monthKey(now: Date): string {
    return now.toISOString().slice(0, 7);
  }

  private async readCursor(): Promise<ProbeCursor> {
    return this.cursors.read<ProbeCursor>('mapbox_probe', {
      sweepStartIso: null,
      lastSweepDoneIso: null,
      nextIndex: 0,
    });
  }

  /** Requests left this month. */
  private quotaLeft(): number {
    const key = this.monthKey(new Date());
    if (this.quota.monthKey !== key) {
      this.quota = { monthKey: key, count: 0 };
    }
    return this.monthlyCap - this.quota.count;
  }

  /** A failed request still costs quota, so every sent request is charged. */
  private async charge(): Promise<void> {
    this.quotaLeft();
    this.quota.count += 1;
    await this.cursors.write('mapbox_quota', this.quota);
  }

  // ---------------------------------------------------------------- live mode

  @Cron(CronExpression.EVERY_MINUTE)
  async scheduledProbe(): Promise<void> {
    if (this.authFailed || this.liveRunning || !this.token || this.routes.length === 0) return;
    const now = new Date();
    const h = this.vnHour(now);
    if (h < this.hourStart || h >= this.hourEnd) return;

    const cursor = await this.readCursor();
    // A sweep left unfinished (worker stopped) resumes at nextIndex right away.
    const midSweep = cursor.nextIndex > 0;
    if (!midSweep && cursor.sweepStartIso) {
      if (Date.now() - Date.parse(cursor.sweepStartIso) < this.intervalMs) return;
    }

    try {
      await this.sweep(cursor);
    } catch (err) {
      this.logger.error(`Probe sweep failed: ${err instanceof Error ? err.message : err}`);
    }
  }

  /** One sweep over all routes. A second call while one runs (cron + POST) is a no-op. */
  async sweep(cursor?: ProbeCursor): Promise<number> {
    if (this.liveRunning) return 0;
    this.liveRunning = true;
    try {
      return await this.sweepRoutes(cursor ?? (await this.readCursor()));
    } finally {
      this.liveRunning = false;
    }
  }

  private async sweepRoutes(state: ProbeCursor): Promise<number> {
    if (state.nextIndex === 0) {
      state.sweepStartIso = new Date().toISOString();
    }

    let ok = 0;
    let consecutiveErrors = 0;
    while (state.nextIndex < this.routes.length) {
      if (this.quotaLeft() <= 0) {
        this.logger.warn(`Monthly cap ${this.monthlyCap} reached; probes paused until next month`);
        break;
      }
      const route = this.routes[state.nextIndex];
      try {
        const sample = await this.fetchProbe(route);
        await this.persist('mapbox_probe', `probe_${sample.timestamp.slice(0, 10)}.jsonl`, sample);
        ok += 1;
        consecutiveErrors = 0;
      } catch (err) {
        if (err instanceof MapboxAuthError) {
          this.pauseOnAuth(err);
          await this.cursors.write('mapbox_probe', state);
          return ok;
        }
        consecutiveErrors += 1;
        const msg = err instanceof Error ? err.message : String(err);
        this.logger.warn(`Probe skip ${route.routeId}: ${msg}`);
        if (msg.includes('429')) {
          await this.sleep(Math.min(60_000, this.delayMs * 4 * consecutiveErrors));
        }
        if (consecutiveErrors >= 5) {
          this.logger.error('Too many consecutive probe errors; stopping this sweep early');
          await this.cursors.write('mapbox_probe', state);
          return ok;
        }
      }
      state.nextIndex += 1;
      await this.cursors.write('mapbox_probe', state);
      await this.sleep(this.delayMs);
    }

    if (state.nextIndex >= this.routes.length) {
      state.nextIndex = 0;
      state.lastSweepDoneIso = new Date().toISOString();
    }
    await this.cursors.write('mapbox_probe', state);
    this.logger.log(
      `Probe sweep: ${ok} ok | month ${this.quota.monthKey} used ${this.quota.count}/${this.monthlyCap}`,
    );
    return ok;
  }

  // ------------------------------------------------------------- typical mode

  /** VN local "YYYY-MM-DDThh:mm" and its UTC instant for slot `i` of a job. */
  private slotAt(job: TypicalJob, i: number): { local: string; utcMs: number } {
    const perDay = Math.floor(((job.hourEnd - job.hourStart) * 60) / job.stepMin);
    const day = Math.floor(i / perDay);
    const minute = job.hourStart * 60 + (i % perDay) * job.stepMin;
    const [y, m, d] = job.startDate.split('-').map((x) => Number(x));
    const dayUtc = new Date(Date.UTC(y, m - 1, d + day));
    const hh = String(Math.floor(minute / 60)).padStart(2, '0');
    const mm = String(minute % 60).padStart(2, '0');
    return {
      local: `${dayUtc.toISOString().slice(0, 10)}T${hh}:${mm}`,
      utcMs: dayUtc.getTime() + (minute - 7 * 60) * 60_000,
    };
  }

  private nSlots(job: TypicalJob): number {
    return job.days * Math.floor(((job.hourEnd - job.hourStart) * 60) / job.stepMin);
  }

  async typicalStatus(): Promise<{
    job: TypicalJob | null;
    planned: number;
    running: boolean;
    authFailed: boolean;
  }> {
    const job = await this.cursors.read<TypicalJob | null>('mapbox_typical', null);
    return {
      job,
      planned: job ? this.nSlots(job) * this.routes.length : 0,
      running: this.typicalRunning,
      authFailed: this.authFailed,
    };
  }

  /**
   * Queue a typical-traffic job and start it in the background. Refuses when
   * an unfinished job exists (unless `restart`) or when it would exceed the cap.
   */
  async startTypical(
    startDate: string,
    days: number,
    stepMin: number,
    restart: boolean,
  ): Promise<{ started: boolean; reason?: string; planned?: number; quotaLeft?: number }> {
    if (!this.token || this.routes.length === 0) {
      return { started: false, reason: 'no token or no MAPBOX_PROBE_FILE' };
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(startDate) || !(days >= 1) || !(stepMin >= 5)) {
      return { started: false, reason: 'need start=YYYY-MM-DD, days>=1, stepMin>=5' };
    }
    const old = await this.cursors.read<TypicalJob | null>('mapbox_typical', null);
    if (old && !old.doneIso && !restart) {
      return { started: false, reason: 'unfinished job exists; pass restart=1 to replace it' };
    }
    if (this.typicalRunning) {
      return { started: false, reason: 'a typical job is running' };
    }
    const job: TypicalJob = {
      startDate,
      days,
      stepMin,
      hourStart: this.hourStart,
      hourEnd: this.hourEnd,
      slotIndex: 0,
      routeIndex: 0,
      sent: 0,
      skippedPast: 0,
      createdIso: new Date().toISOString(),
      doneIso: null,
    };
    const planned = this.nSlots(job) * this.routes.length;
    const left = this.quotaLeft();
    if (planned > left) {
      return { started: false, reason: 'over monthly cap', planned, quotaLeft: left };
    }
    await this.cursors.write('mapbox_typical', job);
    void this.runTypical();
    return { started: true, planned, quotaLeft: left };
  }

  /** Resumes an unfinished typical job after a restart. */
  @Cron(CronExpression.EVERY_MINUTE)
  async resumeTypical(): Promise<void> {
    if (this.authFailed || this.typicalRunning || !this.token || this.routes.length === 0) return;
    const job = await this.cursors.read<TypicalJob | null>('mapbox_typical', null);
    if (job && !job.doneIso) {
      void this.runTypical();
    }
  }

  private async runTypical(): Promise<void> {
    if (this.typicalRunning) return;
    this.typicalRunning = true;
    try {
      const job = await this.cursors.read<TypicalJob | null>('mapbox_typical', null);
      if (!job || job.doneIso) return;
      const total = this.nSlots(job);
      const file = `typical_${job.startDate}.jsonl`;
      let consecutiveErrors = 0;
      while (job.slotIndex < total) {
        const slot = this.slotAt(job, job.slotIndex);
        // Mapbox answers depart_at from its historic profile; keep slots in the future.
        if (slot.utcMs < Date.now() + 10 * 60_000) {
          job.skippedPast += this.routes.length - job.routeIndex;
          job.slotIndex += 1;
          job.routeIndex = 0;
          await this.cursors.write('mapbox_typical', job);
          continue;
        }
        if (this.quotaLeft() <= 0) {
          this.logger.warn('Monthly cap reached; typical job paused until next month');
          return;
        }
        const route = this.routes[job.routeIndex];
        try {
          const sample = await this.fetchProbe(route, slot.local);
          await this.persist('mapbox_typical', file, sample);
          consecutiveErrors = 0;
        } catch (err) {
          if (err instanceof MapboxAuthError) {
            this.pauseOnAuth(err);
            await this.cursors.write('mapbox_typical', job);
            return;
          }
          job.failed = (job.failed ?? 0) + 1;
          consecutiveErrors += 1;
          const msg = err instanceof Error ? err.message : String(err);
          this.logger.warn(`Typical skip ${route.routeId} @${slot.local}: ${msg}`);
          if (msg.includes('429')) {
            await this.sleep(Math.min(60_000, 2000 * consecutiveErrors));
          }
          if (consecutiveErrors >= 10) {
            this.logger.error('Too many consecutive typical errors; pausing (cron retries)');
            await this.cursors.write('mapbox_typical', job);
            return;
          }
        }
        job.sent += 1;
        job.routeIndex += 1;
        if (job.routeIndex >= this.routes.length) {
          job.routeIndex = 0;
          job.slotIndex += 1;
          this.logger.log(
            `Typical slot ${job.slotIndex}/${total} done (${slot.local}) | ` +
              `month used ${this.quota.count}/${this.monthlyCap}`,
          );
        }
        await this.cursors.write('mapbox_typical', job);
        await this.sleep(this.typicalDelayMs);
      }
      job.doneIso = new Date().toISOString();
      await this.cursors.write('mapbox_typical', job);
      this.logger.log(
        `Typical job ${job.startDate} done: ${job.sent} sent, ${job.skippedPast} past`,
      );
    } catch (err) {
      this.logger.error(`Typical job failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      this.typicalRunning = false;
    }
  }

  // ------------------------------------------------------------------ shared

  private pauseOnAuth(err: Error): void {
    if (!this.authFailed) {
      this.logger.error(
        `${err.message}. Live and typical probes PAUSED; cursors not advanced. ` +
          'Put a valid MAPBOX_ACCESS_TOKEN in .env and restart the worker.',
      );
    }
    this.authFailed = true;
  }

  private async fetchProbe(route: ProbeRoute, departAt?: string): Promise<ProbeSample> {
    const n = route.coordinates.length;
    const coords = route.coordinates.join(';');
    // Congestion annotations exist only on the traffic profile.
    const annotations =
      this.profile === 'driving-traffic'
        ? 'duration,distance,speed,congestion,congestion_numeric'
        : 'duration,distance,speed';
    // Via points guide the path without new legs; Mapbox requires steps=true for that.
    const via = n > 2;
    let url =
      `https://api.mapbox.com/directions/v5/mapbox/${this.profile}/${coords}` +
      `?alternatives=false&geometries=geojson&overview=full&steps=${via}` +
      `&annotations=${annotations}`;
    if (via) {
      url += `&waypoints=0;${n - 1}`;
    }
    if (route.bearings && route.bearings.length === n) {
      url += `&bearings=${route.bearings.map((b) => encodeURIComponent(b)).join(';')}`;
    }
    if (departAt) {
      url += `&depart_at=${encodeURIComponent(departAt)}`;
    }
    url += `&access_token=${encodeURIComponent(this.token)}`;

    const requestedAt = new Date().toISOString();
    await this.charge();
    const res = await fetch(url);
    if (res.status === 429) {
      throw new Error(`Mapbox HTTP 429 rate limit for ${route.routeId}`);
    }
    if (res.status === 401 || res.status === 403) {
      const detail = (await res.text()).slice(0, 200);
      throw new MapboxAuthError(`Mapbox HTTP ${res.status} (token): ${detail}`);
    }
    if (!res.ok) {
      const detail = (await res.text()).slice(0, 200);
      throw new Error(`Mapbox HTTP ${res.status} for ${route.routeId}: ${detail}`);
    }
    const body = (await res.json()) as {
      routes?: Array<{
        duration: number;
        distance: number;
        geometry?: { coordinates: number[][] };
        legs?: Array<{ annotation?: Record<string, unknown[]> }>;
      }>;
    };
    const r = body.routes?.[0];
    if (!r) {
      throw new Error(`No route for ${route.routeId}`);
    }
    return {
      timestamp: requestedAt,
      routeId: route.routeId,
      profile: this.profile,
      ...(departAt ? { departAt } : {}),
      durationSec: r.duration,
      distanceM: r.distance,
      geometry: r.geometry?.coordinates ?? [],
      legs: (r.legs ?? []).map((leg) => leg.annotation ?? {}),
    };
  }

  private async persist(dir: string, name: string, sample: ProbeSample): Promise<void> {
    const full = this.csv.resolve(dir, name);
    await fs.mkdir(path.dirname(full), { recursive: true });
    await fs.appendFile(full, `${JSON.stringify(sample)}\n`, 'utf8');
  }
}
