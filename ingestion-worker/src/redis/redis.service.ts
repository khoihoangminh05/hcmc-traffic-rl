import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  readonly client: Redis;

  constructor(private readonly config: ConfigService) {
    const url = this.config.get<string>('REDIS_URL', 'redis://localhost:6379');
    this.client = new Redis(url, {
      maxRetriesPerRequest: 3,
      lazyConnect: true,
    });
    this.client.on('error', (err: Error) => {
      this.logger.warn(`Redis error: ${err.message}`);
    });
  }

  async connect(): Promise<void> {
    if (this.client.status === 'ready' || this.client.status === 'connecting') {
      return;
    }
    await this.client.connect();
  }

  async ping(): Promise<string> {
    try {
      if (this.client.status !== 'ready') {
        await this.client.connect();
      }
      return await this.client.ping();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'unreachable';
      throw new Error(message);
    }
  }

  async onModuleDestroy(): Promise<void> {
    await this.client.quit();
  }
}
