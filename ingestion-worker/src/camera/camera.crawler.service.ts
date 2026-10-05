import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Cron, CronExpression } from '@nestjs/schedule';
import { RedisService } from '../redis/redis.service';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';
import { CameraCursor, CameraSource } from './camera.types';

@Injectable()
export class CameraCrawlerService implements OnModuleInit {
  private readonly logger = new Logger(CameraCrawlerService.name);
  private running = false;
  private sources: CameraSource[] = [];
  private readonly segmentLimit: number;

  constructor(
    private readonly config: ConfigService,
    private readonly redis: RedisService,
    private readonly cursors: CursorStore,
    private readonly csv: CsvWriter,
  ) {
    this.segmentLimit = Number(this.config.get<string>('CAMERA_SEGMENT_LIMIT', '30'));
  }

  async onModuleInit(): Promise<void> {
    this.sources = await this.loadSources();
    this.logger.log(`Camera sources loaded: ${this.sources.length}`);
  }

  private async loadSources(): Promise<CameraSource[]> {
    const file = this.config.get<string>('CAMERA_CATALOG_FILE', '');
    if (file) {
      try {
        const raw = await fs.readFile(path.resolve(file), 'utf8');
        const parsed = JSON.parse(raw) as CameraSource[];
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      } catch (err) {
        this.logger.warn(
          `CAMERA_CATALOG_FILE unreadable (${err instanceof Error ? err.message : err})`,
        );
      }
    }
    try {
      const envRaw = this.config.get<string>('CAMERA_HLS_SOURCES', '[]');
      const parsed = JSON.parse(envRaw) as CameraSource[];
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      this.logger.warn('CAMERA_HLS_SOURCES is not valid JSON; crawler idle');
      return [];
    }
  }

  @Cron(CronExpression.EVERY_5_MINUTES)
  async scheduledCrawl(): Promise<void> {
    if (this.running || this.sources.length === 0) return;
    this.running = true;
    try {
      await this.crawlOnce();
    } catch (err) {
      this.logger.error(`Camera crawl failed: ${err instanceof Error ? err.message : err}`);
    } finally {
      this.running = false;
    }
  }

  async crawlOnce(): Promise<{ cameraId: string; segments: number }[]> {
    if (this.sources.length === 0) {
      this.sources = await this.loadSources();
    }
    const cursor = await this.cursors.read<CameraCursor>('camera', {
      lastSegmentUriByCamera: {},
      lastSuccessIsoByCamera: {},
    });
    const results: { cameraId: string; segments: number }[] = [];

    for (const source of this.sources) {
      const mode = source.mode ?? (source.url.includes('ImageHandler.ashx') ? 'snapshot' : 'hls');
      const n =
        mode === 'snapshot'
          ? await this.crawlSnapshot(source, cursor)
          : await this.crawlHls(source, cursor);
      results.push({ cameraId: source.cameraId, segments: n });
    }

    await this.cursors.write('camera', cursor);
    return results;
  }

  /** HCMC portal: JPEG snapshot refreshed ~every few seconds (not HLS). */
  private async crawlSnapshot(source: CameraSource, cursor: CameraCursor): Promise<number> {
    const day = new Date().toISOString().slice(0, 10);
    const outDir = this.csv.resolve('camera', source.cameraId, day);
    await fs.mkdir(outDir, { recursive: true });
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    const fileName = `snap_${stamp}.jpg`;
    const buf = await this.fetchBuffer(source.url);
    await fs.writeFile(path.join(outDir, fileName), buf);
    cursor.lastSegmentUriByCamera[source.cameraId] = fileName;
    cursor.lastSuccessIsoByCamera[source.cameraId] = new Date().toISOString();
    await this.publishMeta(source.cameraId, 1, outDir, cursor.lastSuccessIsoByCamera[source.cameraId]);
    this.logger.log(`Camera ${source.cameraId}: snapshot -> ${outDir}/${fileName}`);
    return 1;
  }

  private async crawlHls(source: CameraSource, cursor: CameraCursor): Promise<number> {
    const playlist = await this.fetchText(source.url);
    const baseUrl = source.url.replace(/[^/]+$/, '');
    const segmentUris = playlist
      .split(/\r?\n/)
      .map((l) => l.trim())
      .filter((l) => l && !l.startsWith('#'));

    const lastSeen = cursor.lastSegmentUriByCamera[source.cameraId];
    let startIdx = 0;
    if (lastSeen) {
      const idx = segmentUris.indexOf(lastSeen);
      startIdx = idx >= 0 ? idx + 1 : 0;
    }

    const toFetch = segmentUris.slice(startIdx, startIdx + this.segmentLimit);
    if (toFetch.length === 0) {
      this.logger.debug(`No new segments for ${source.cameraId}`);
      return 0;
    }

    const day = new Date().toISOString().slice(0, 10);
    const outDir = this.csv.resolve('camera', source.cameraId, day);
    await fs.mkdir(outDir, { recursive: true });

    let saved = 0;
    for (const uri of toFetch) {
      const abs = uri.startsWith('http') ? uri : new URL(uri, baseUrl).toString();
      const buf = await this.fetchBuffer(abs);
      const name = sanitizeName(uri);
      await fs.writeFile(path.join(outDir, name), buf);
      cursor.lastSegmentUriByCamera[source.cameraId] = uri;
      saved += 1;
    }

    cursor.lastSuccessIsoByCamera[source.cameraId] = new Date().toISOString();
    await this.publishMeta(source.cameraId, saved, outDir, cursor.lastSuccessIsoByCamera[source.cameraId]);
    this.logger.log(`Camera ${source.cameraId}: saved ${saved} HLS segments -> ${outDir}`);
    return saved;
  }

  private async publishMeta(
    cameraId: string,
    segments: number,
    dir: string,
    at: string,
  ): Promise<void> {
    try {
      await this.redis.connect();
      await this.redis.client.publish(
        `ingest:camera:${cameraId}`,
        JSON.stringify({ cameraId, segments, dir, at }),
      );
    } catch (err) {
      this.logger.warn(`Redis publish skipped: ${err instanceof Error ? err.message : err}`);
    }
  }

  private async fetchText(url: string): Promise<string> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HLS playlist HTTP ${res.status}: ${url}`);
    return res.text();
  }

  private async fetchBuffer(url: string): Promise<Buffer> {
    const res = await fetch(url, { redirect: 'follow' });
    if (!res.ok) throw new Error(`Camera HTTP ${res.status}: ${url}`);
    return Buffer.from(await res.arrayBuffer());
  }
}

function sanitizeName(uri: string): string {
  const base = uri.split('/').pop() ?? `seg_${Date.now()}.ts`;
  return base.replace(/[^a-zA-Z0-9._-]/g, '_');
}
