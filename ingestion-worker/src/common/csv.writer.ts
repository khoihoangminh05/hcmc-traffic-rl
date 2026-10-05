import { promises as fs } from 'fs';
import * as path from 'path';
import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/** RFC-style CSV escape: quote fields that contain comma/quote/newline. */
export function csvEscape(value: string | number): string {
  const s = String(value);
  if (/[",\n\r]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

@Injectable()
export class CsvWriter {
  private readonly dataRawDir: string;

  constructor(config: ConfigService) {
    this.dataRawDir = path.resolve(config.get<string>('DATA_RAW_DIR', './data_raw'));
  }

  async append(relativePath: string, header: string, row: string): Promise<string> {
    const full = path.join(this.dataRawDir, relativePath);
    await fs.mkdir(path.dirname(full), { recursive: true });
    try {
      await fs.access(full);
    } catch {
      await fs.writeFile(full, `${header}\n`, 'utf8');
    }
    await fs.appendFile(full, `${row}\n`, 'utf8');
    return full;
  }

  /** Append a row from field values (auto-escaped). */
  async appendRow(
    relativePath: string,
    headers: string[],
    values: Array<string | number>,
  ): Promise<string> {
    return this.append(
      relativePath,
      headers.map(csvEscape).join(','),
      values.map(csvEscape).join(','),
    );
  }

  resolve(...parts: string[]): string {
    return path.join(this.dataRawDir, ...parts);
  }

  get root(): string {
    return this.dataRawDir;
  }
}
