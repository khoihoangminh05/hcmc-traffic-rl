import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { CsvWriter } from '../common/csv.writer';

export interface SyncManifest {
  generatedAt: string;
  root: string;
  files: Array<{ relativePath: string; sizeBytes: number; mtimeIso: string }>;
}

@Injectable()
export class SyncManifestService {
  private readonly logger = new Logger(SyncManifestService.name);

  constructor(private readonly csv: CsvWriter) {}

  @Cron(CronExpression.EVERY_HOUR)
  async scheduled(): Promise<void> {
    await this.writeManifest();
  }

  async writeManifest(): Promise<SyncManifest> {
    const files: SyncManifest['files'] = [];
    await this.walk(this.csv.root, this.csv.root, files);
    const manifest: SyncManifest = {
      generatedAt: new Date().toISOString(),
      root: this.csv.root,
      files,
    };
    const out = path.join(this.csv.root, 'sync_manifest.json');
    await fs.mkdir(this.csv.root, { recursive: true });
    await fs.writeFile(out, JSON.stringify(manifest, null, 2), 'utf8');
    this.logger.log(`Sync manifest: ${files.length} files → ${out}`);
    return manifest;
  }

  private async walk(
    root: string,
    dir: string,
    out: SyncManifest['files'],
  ): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        await this.walk(root, full, out);
        continue;
      }
      if (entry.name === 'sync_manifest.json' || entry.name === '.gitkeep') continue;
      const stat = await fs.stat(full);
      out.push({
        relativePath: path.relative(root, full).replace(/\\/g, '/'),
        sizeBytes: stat.size,
        mtimeIso: stat.mtime.toISOString(),
      });
    }
  }
}
