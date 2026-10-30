import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Cron, CronExpression } from '@nestjs/schedule';
import { RedisService } from '../redis/redis.service';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';
import { MapboxCursor, OdPair, TravelTimeSample } from './mapbox.types';

/**
 * Gentle Mapbox poller — never dumps the full OD list in one burst.
 *
 * Defaults (override via .env):
 * - MAPBOX_POLL_INTERVAL_MS=900000  (15 min between cycles)
 * - MAPBOX_BATCH_SIZE=15            (max OD per cycle)
 * - MAPBOX_REQUEST_DELAY_MS=1500    (gap between HTTP calls)
 */
@Injectable()
export class MapboxPollerService implements OnModuleInit {
  private readonly logger = new Logger(MapboxPollerService.name);
  private running = false;
  private token: string;
  private pairs: OdPair[] = [];
  private readonly minIntervalMs: number;
  private readonly batchSize: number;
  private readonly requestDelayMs: number;

  constructor(
    private readonly config: ConfigService,
    private readonly redis: RedisService,
    private readonly cursors: CursorStore,
    private readonly csv: CsvWriter,
  ) {
    this.token = this.config.get<string>('MAPBOX_ACCESS_TOKEN', '');
    this.minIntervalMs = Number(this.config.get<string>('MAPBOX_POLL_INTERVAL_MS', '900000'));
    this.batchSize = Math.max(1, Number(this.config.get<string>('MAPBOX_BATCH_SIZE', '15')));
    this.requestDelayMs = Math.max(
      500,
      Number(this.config.get<string>('MAPBOX_REQUEST_DELAY_MS', '1500')),
    );
  }

  async onModuleInit(): Promise<void> {
    this.token = this.config.get<string>('MAPBOX_ACCESS_TOKEN', '');
    this.pairs = await this.loadPairs();
    this.logger.log(
      `Mapbox ready: ${this.pairs.length} ODs | batch=${this.batchSize} | ` +
        `delay=${this.requestDelayMs}ms | cycle≥${this.minIntervalMs}ms`,
    );
  }

  private async loadPairs(): Promise<OdPair[]> {
    const file = this.config.get<string>('MAPBOX_OD_FILE', '');
    if (file) {
      try {
        const raw = await fs.readFile(path.resolve(file), 'utf8');
        const parsed = JSON.parse(raw) as OdPair[];
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      } catch (err) {
        this.logger.warn(
          `MAPBOX_OD_FILE unreadable (${err instanceof Error ? err.message : err}); falling back to env`,
        );
      }
    }
    return this.parsePairs(this.config.get<string>('MAPBOX_OD_PAIRS', '[]'));
  }

  private parsePairs(raw: string): OdPair[] {
    try {
      const parsed = JSON.parse(raw) as OdPair[];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      this.logger.warn('MAPBOX_OD_PAIRS is not valid JSON; poller idle');
      return [];
    }
  }

  private async sleep(ms: number): Promise<void> {
    await new Promise((r) => setTimeout(r, ms));
  }

  @Cron(CronExpression.EVERY_MINUTE)
  async scheduledPoll(): Promise<void> {
    if (this.running) return;
    if (!this.token || this.pairs.length === 0) return;

    const cursor = await this.cursors.read<MapboxCursor>('mapbox', {
      lastPollIso: null,
      lastSuccessByOd: {},
      nextIndex: 0,
    });
    if (cursor.lastPollIso) {
      const elapsed = Date.now() - Date.parse(cursor.lastPollIso);
      if (elapsed < this.minIntervalMs) return;
    }

    this.running = true;
    try {
      await this.pollOnce(cursor, false);
    } catch (err) {
      this.logger.error(`Mapbox poll failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      this.running = false;
    }
  }

  /**
   * @param fullSweep if true (manual POST), still respects batchSize unless override via env MAPBOX_MANUAL_FULL=1
   */
  async pollOnce(
    cursor?: MapboxCursor,
    fullSweep = false,
  ): Promise<TravelTimeSample[]> {
    if (this.pairs.length === 0) {
      this.pairs = await this.loadPairs();
    }
    if (!this.token || this.pairs.length === 0) {
      this.logger.warn('Mapbox poll skipped: missing token or OD pairs');
      return [];
    }

    const state =
      cursor ??
      (await this.cursors.read<MapboxCursor>('mapbox', {
        lastPollIso: null,
        lastSuccessByOd: {},
        nextIndex: 0,
      }));
    if (typeof state.nextIndex !== 'number') state.nextIndex = 0;

    const allowFull =
      fullSweep && this.config.get<string>('MAPBOX_MANUAL_FULL', '0') === '1';
    const limit = allowFull ? this.pairs.length : Math.min(this.batchSize, this.pairs.length);

    const samples: TravelTimeSample[] = [];
    let idx = state.nextIndex % this.pairs.length;
    let consecutiveErrors = 0;

    this.logger.log(
      `Mapbox cycle start: ${limit}/${this.pairs.length} ODs from index ${idx} ` +
        `(delay ${this.requestDelayMs}ms)`,
    );

    for (let n = 0; n < limit; n++) {
      const pair = this.pairs[idx];
      try {
        const sample = await this.fetchDirections(pair);
        samples.push(sample);
        await this.persistSample(sample);
        state.lastSuccessByOd[pair.odId] = sample.timestamp;
        consecutiveErrors = 0;
      } catch (err) {
        consecutiveErrors += 1;
        const msg = err instanceof Error ? err.message : String(err);
        this.logger.warn(`Mapbox skip ${pair.odId}: ${msg}`);
        if (msg.includes('429') || msg.toLowerCase().includes('rate')) {
          const backoff = Math.min(60_000, this.requestDelayMs * 4 * consecutiveErrors);
          this.logger.warn(`Rate limited — backing off ${backoff}ms`);
          await this.sleep(backoff);
        }
        if (consecutiveErrors >= 5) {
          this.logger.error('Too many consecutive Mapbox errors — stopping this cycle early');
          break;
        }
      }

      idx = (idx + 1) % this.pairs.length;
      if (n < limit - 1) {
        await this.sleep(this.requestDelayMs);
      }
    }

    state.nextIndex = idx;
    state.lastPollIso = new Date().toISOString();
    await this.cursors.write('mapbox', state);
    this.logger.log(
      `Mapbox cycle done: ${samples.length} ok, nextIndex=${state.nextIndex}`,
    );
    return samples;
  }

  private async fetchDirections(pair: OdPair): Promise<TravelTimeSample> {
    const coords = `${pair.origin};${pair.destination}`;
    const url =
      `https://api.mapbox.com/directions/v5/mapbox/driving/${coords}` +
      `?overview=false&access_token=${encodeURIComponent(this.token)}`;

    const res = await fetch(url);
    if (res.status === 429) {
      throw new Error(`Mapbox HTTP 429 rate limit for ${pair.odId}`);
    }
    if (!res.ok) {
      throw new Error(`Mapbox HTTP ${res.status} for ${pair.odId}`);
    }
    const body = (await res.json()) as {
      routes?: Array<{ duration: number; distance: number }>;
    };
    const route = body.routes?.[0];
    if (!route) {
      throw new Error(`No route for ${pair.odId}`);
    }

    return {
      timestamp: new Date().toISOString(),
      odId: pair.odId,
      origin: pair.origin,
      destination: pair.destination,
      durationSec: route.duration,
      distanceM: route.distance,
    };
  }

  private async persistSample(sample: TravelTimeSample): Promise<void> {
    const day = sample.timestamp.slice(0, 10);
    await this.csv.appendRow(
      pathJoin('mapbox', `travel_time_${day}.csv`),
      ['timestamp', 'od_id', 'origin', 'destination', 'duration_sec', 'distance_m'],
      [
        sample.timestamp,
        sample.odId,
        sample.origin,
        sample.destination,
        sample.durationSec,
        sample.distanceM,
      ],
    );

    if (!this.redis.enabled) return;
    try {
      const key = `travel:${sample.odId}`;
      await this.redis.connect();
      await this.redis.client.lpush(key, JSON.stringify(sample));
      await this.redis.client.ltrim(key, 0, 999);
      await this.redis.client.set(`travel:last:${sample.odId}`, sample.timestamp);
    } catch (err) {
      this.logger.warn(`Redis persist skipped: ${err instanceof Error ? err.message : err}`);
    }
  }
}

function pathJoin(...parts: string[]): string {
  return parts.join('/');
}
