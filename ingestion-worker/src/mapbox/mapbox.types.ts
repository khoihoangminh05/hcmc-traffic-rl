export interface OdPair {
  odId: string;
  /** lon,lat */
  origin: string;
  /** lon,lat */
  destination: string;
}

export interface TravelTimeSample {
  timestamp: string;
  odId: string;
  origin: string;
  destination: string;
  durationSec: number;
  distanceM: number;
}

export interface MapboxCursor {
  lastPollIso: string | null;
  lastSuccessByOd: Record<string, string>;
  /** Round-robin index into OD list (avoids blasting all seeds each cycle). */
  nextIndex: number;
}
