import { Controller, Post } from '@nestjs/common';
import { SyncManifestService } from './sync.manifest.service';

@Controller('sync')
export class SyncController {
  constructor(private readonly sync: SyncManifestService) {}

  @Post('manifest')
  async manifest() {
    return this.sync.writeManifest();
  }
}
