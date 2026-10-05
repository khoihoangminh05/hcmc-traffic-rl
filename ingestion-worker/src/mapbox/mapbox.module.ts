import { Module } from '@nestjs/common';
import { MapboxPollerService } from './mapbox.poller.service';
import { MapboxController } from './mapbox.controller';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';

@Module({
  providers: [MapboxPollerService, CursorStore, CsvWriter],
  controllers: [MapboxController],
  exports: [MapboxPollerService],
})
export class MapboxModule {}
