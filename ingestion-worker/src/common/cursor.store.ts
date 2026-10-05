import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/** Durable cursor store so Node 1 can pause / resume safely. */
@Injectable()
export class CursorStore {
  private readonly logger = new Logger(CursorStore.name);
  private readonly stateDir: string;

  constructor(config: ConfigService) {
    this.stateDir = path.resolve(config.get<string>('STATE_DIR', './state'));
  }

  private fileFor(key: string): string {
    return path.join(this.stateDir, `${key}.json`);
  }

  async read<T>(key: string, fallback: T): Promise<T> {
    const file = this.fileFor(key);
    try {
      const raw = await fs.readFile(file, 'utf8');
      return JSON.parse(raw) as T;
    } catch {
      return fallback;
    }
  }

  async write<T>(key: string, value: T): Promise<void> {
    await fs.mkdir(this.stateDir, { recursive: true });
    const file = this.fileFor(key);
    await fs.writeFile(file, JSON.stringify(value, null, 2), 'utf8');
    this.logger.debug(`cursor saved: ${key}`);
  }
}
