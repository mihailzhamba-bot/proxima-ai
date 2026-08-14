import type { Decimal } from 'decimal.js';

export const SIGNAL_TIMEZONE = 'Europe/Moscow' as const;
export const SIGNAL_WINDOW_DAYS = 14;

export type SignalSource = 'official_wb_statistics' | 'official_wb_analytics' | 'official_wb_finance';
export type SignalRunStatus = 'RUNNING' | 'NO_SIGNAL' | 'BLOCKED' | 'READY' | 'SENT' | 'SEND_FAILED';

export interface ProductConfig {
  tenantId: string;
  nmId: bigint;
  internalArticle: string;
  cogsRub: Decimal;
  leadTimeDays: number;
  safetyBufferDays: number;
  effectiveFrom: string;
}

export interface WarehouseMap {
  tenantId: string;
  salesWarehouseName: string;
  stockWarehouseName: string;
  canonicalWarehouse: string;
  effectiveFrom: string;
}

export interface SignalWindow {
  from: string;
  to: string;
}

export interface RawArtifactRecord {
  rawArtifactId: string;
  runId: string;
  source: SignalSource;
  stage: string;
  pageSequence: number;
  endpointPath: string;
  httpStatus: number;
  responseHeaders: Record<string, string>;
  contentSha256: string;
  contentSize: number;
  objectLocator: string;
  manifestSha256: string;
  retrievedAt: Date;
}

export interface SignalCandidate {
  nmId: bigint;
  internalArticle: string;
  warehouse: string;
  stockQuantity: number;
  velocityUnitsPerDay: Decimal;
  daysCover: number;
  leadTimeDays: number;
  safetyBufferDays: number;
  thresholdDays: number;
  marginPerUnitRub: Decimal;
  stockAsOf: Date;
}

export interface SignalRepository {
  createRun(runId: string, tenantId: string, window: SignalWindow): Promise<void>;
  loadProductConfig(tenantId: string, asOf: string): Promise<ProductConfig[]>;
  loadWarehouseMap(tenantId: string, asOf: string): Promise<WarehouseMap[]>;
  recordRawArtifact(record: RawArtifactRecord): Promise<void>;
  completeRun(runId: string, status: Extract<SignalRunStatus, 'NO_SIGNAL' | 'BLOCKED'>, reason: string): Promise<void>;
  markReady(runId: string, candidate: SignalCandidate): Promise<void>;
  recordTelegramResult(runId: string, attemptedAt: Date, messageId: bigint | null): Promise<void>;
}

export class BusinessSignalError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
    this.name = 'BusinessSignalError';
  }
}
