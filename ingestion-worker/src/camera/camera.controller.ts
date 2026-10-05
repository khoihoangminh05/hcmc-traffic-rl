import { Controller, Post } from '@nestjs/common';
import { CameraCrawlerService } from './camera.crawler.service';

@Controller('camera')
export class CameraController {
  constructor(private readonly crawler: CameraCrawlerService) {}

  @Post('crawl')
  async crawl() {
    const results = await this.crawler.crawlOnce();
    return { results };
  }
}
