import { Controller, Post } from '@nestjs/common';
import { MapboxPollerService } from './mapbox.poller.service';

@Controller('mapbox')
export class MapboxController {
  constructor(private readonly poller: MapboxPollerService) {}

  /** Manual trigger for smoke tests / resume after pause. */
  @Post('poll')
  async poll() {
    const samples = await this.poller.pollOnce();
    return { count: samples.length, samples };
  }
}
