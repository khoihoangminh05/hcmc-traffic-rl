import { Controller, Get } from '@nestjs/common';
import { RedisService } from '../redis/redis.service';

@Controller('health')
export class HealthController {
  constructor(private readonly redis: RedisService) {}

  @Get()
  async check(): Promise<{ status: string; redis: string }> {
    try {
      const pong = await this.redis.ping();
      return { status: 'ok', redis: pong };
    } catch (err) {
      const message = err instanceof Error ? err.message : 'unknown';
      return { status: 'degraded', redis: message };
    }
  }
}
