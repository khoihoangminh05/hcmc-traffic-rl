import { Module } from '@nestjs/common';
import { MapboxPollerService } from './mapbox.poller.service';
import { MapboxProbeService } from './mapbox.probe.service';
import { MapboxController } from './mapbox.controller';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';

@Module({
  providers: [MapboxPollerService, MapboxProbeService, CursorStore, CsvWriter],
  controllers: [MapboxController],
  exports: [MapboxPollerService, MapboxProbeService],
})
export class MapboxModule {}
