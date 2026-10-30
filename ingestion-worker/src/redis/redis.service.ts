import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  readonly client: Redis;
  /** REDIS_URL= (empty) turns Redis off, e.g. on sol1 where only the probes run. */
  readonly enabled: boolean;
  private lastError = '';

  constructor(private readonly config: ConfigService) {
    const url = this.config.get<string>('REDIS_URL', 'redis://localhost:6379');
    this.enabled = url !== '';
    this.client = new Redis(url || 'redis://localhost:6379', {
      maxRetriesPerRequest: 3,
      lazyConnect: true,
      // Give up after a few reconnects; the next connect() call tries again.
      retryStrategy: (times: number) => (times > 3 ? null : 1000 * times),
    });
    this.client.on('error', (err: Error) => {
      if (err.message !== this.lastError) {
        this.lastError = err.message;
        this.logger.warn(`Redis error: ${err.message}`);
      }
    });
    this.client.on('ready', () => {
      this.lastError = '';
    });
    if (!this.enabled) {
      this.logger.log('Redis disabled (REDIS_URL empty)');
    }
  }

  async connect(): Promise<void> {
    if (!this.enabled) {
      throw new Error('Redis disabled');
    }
    if (this.client.status === 'ready' || this.client.status === 'connecting') {
      return;
    }
    await this.client.connect();
  }

  async ping(): Promise<string> {
    try {
      await this.connect();
      return await this.client.ping();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'unreachable';
      throw new Error(message);
    }
  }

  async onModuleDestroy(): Promise<void> {
    if (this.client.status === 'ready') {
      await this.client.quit();
    } else {
      this.client.disconnect();
    }
  }
}
