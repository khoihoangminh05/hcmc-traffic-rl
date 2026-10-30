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

/** One long probe route (see ml-core/data_fusion/design_probe_routes.py). */
export interface ProbeRoute {
  routeId: string;
  /** "lon,lat" strings: origin, via points on alley edges, destination (25 max). */
  coordinates: string[];
  /** Mapbox `bearings` item per coordinate ("angle,range"; "" = unconstrained). */
  bearings?: string[];
  nodes?: string[];
  length_m?: number;
  expected_alley_ids?: string[];
}

/** Raw driving-traffic response, kept whole for offline edge matching. */
export interface ProbeSample {
  timestamp: string;
  routeId: string;
  profile: string;
  /** Typical-traffic samples only: requested departure, VN local "YYYY-MM-DDThh:mm". */
  departAt?: string;
  durationSec: number;
  distanceM: number;
  /** [lon, lat] per vertex of the full route geometry. */
  geometry: number[][];
  /** Per-leg annotation arrays (duration, distance, speed, congestion, ...), one value per segment. */
  legs: Array<Record<string, unknown[]>>;
}

export interface ProbeCursor {
  sweepStartIso: string | null;
  lastSweepDoneIso: string | null;
  /** Next route in the current sweep; > 0 means a sweep was interrupted. */
  nextIndex: number;
  /** Pre-quota-cursor files kept the monthly count here; read once for migration. */
  monthKey?: string;
  monthCount?: number;
}

/** Requests sent this calendar month (UTC) by live and typical probes together. */
export interface QuotaCursor {
  monthKey: string;
  count: number;
}

/** A typical-traffic job: every route at every `depart_at` slot of `days` future days. */
export interface TypicalJob {
  /** First day, VN local YYYY-MM-DD. */
  startDate: string;
  days: number;
  stepMin: number;
  hourStart: number;
  hourEnd: number;
  /** Resume position. */
  slotIndex: number;
  routeIndex: number;
  sent: number;
  skippedPast: number;
  createdIso: string;
  doneIso: string | null;
}
