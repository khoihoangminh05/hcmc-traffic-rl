import { Module } from '@nestjs/common';
import { SyncManifestService } from './sync.manifest.service';
import { SyncController } from './sync.controller';
import { CsvWriter } from '../common/csv.writer';

@Module({
  providers: [SyncManifestService, CsvWriter],
  controllers: [SyncController],
})
export class SyncModule {}
