import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';
import { RedisModule } from './redis/redis.module';
import { HealthModule } from './health/health.module';
import { MapboxModule } from './mapbox/mapbox.module';
import { CameraModule } from './camera/camera.module';
import { SyncModule } from './sync/sync.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: ['.env'],
    }),
    ScheduleModule.forRoot(),
    RedisModule,
    HealthModule,
    MapboxModule,
    CameraModule,
    SyncModule,
  ],
})
export class AppModule {}
