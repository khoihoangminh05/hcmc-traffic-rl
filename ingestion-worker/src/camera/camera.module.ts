import { Module } from '@nestjs/common';
import { CameraCrawlerService } from './camera.crawler.service';
import { CameraController } from './camera.controller';
import { CursorStore } from '../common/cursor.store';
import { CsvWriter } from '../common/csv.writer';

@Module({
  providers: [CameraCrawlerService, CursorStore, CsvWriter],
  controllers: [CameraController],
  exports: [CameraCrawlerService],
})
export class CameraModule {}
