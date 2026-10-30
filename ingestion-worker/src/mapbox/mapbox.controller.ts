import { Controller, Get, Post, Query } from '@nestjs/common';
import { MapboxPollerService } from './mapbox.poller.service';
import { MapboxProbeService } from './mapbox.probe.service';

@Controller('mapbox')
export class MapboxController {
  constructor(
    private readonly poller: MapboxPollerService,
    private readonly probes: MapboxProbeService,
  ) {}

  /** Manual trigger for smoke tests / resume after pause. */
  @Post('poll')
  async poll() {
    const samples = await this.poller.pollOnce();
    return { count: samples.length, samples };
  }

  /** Manual probe sweep (resumes an interrupted sweep; counts toward the monthly cap). */
  @Post('probe')
  async probe() {
    const ok = await this.probes.sweep();
    return { ok };
  }

  /**
   * Queue Mapbox typical traffic for future days (runs in the background, resumable).
   * Example: POST /mapbox/probe/typical?start=2026-11-02&days=7&stepMin=15
   */
  @Post('probe/typical')
  async typical(
    @Query('start') start: string,
    @Query('days') days = '7',
    @Query('stepMin') stepMin = '15',
    @Query('restart') restart = '0',
  ) {
    return this.probes.startTypical(start, Number(days), Number(stepMin), restart === '1');
  }

  @Get('probe/typical')
  async typicalStatus() {
    return this.probes.typicalStatus();
  }
}
