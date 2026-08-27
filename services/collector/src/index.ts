export {
  AuthRequiredError,
  attachSecondaryError,
  isAuthRequiredError,
  isLoginUrl,
} from './imported/auth-error.js';
export {
  MANAGED_OPEN_FLAGS,
  UnsafePathError,
  assertManagedDirectory,
  assertManagedFile,
  ensureManagedPrivateDir,
  openManagedDirectory,
  openManagedFile,
  readManagedFile,
} from './imported/path-safety.js';
export {
  errorDiagnostic,
  redactString,
  redactValue,
  sanitizeUrl,
  type ErrorDiagnostic,
} from './imported/redact.js';
export {
  assertSourceArtifactContract,
  canonicalJson,
  canonicalManifestBytes,
  createManualWbXlsxManifest,
  sha256,
} from './intake/manifest.js';
export { intakeManualWbXlsx } from './intake/manual-wb-xlsx.js';
export {
  IntakeError,
  MANUAL_EXPORT_RETRIEVAL_MODE,
  OFFICIAL_WB_MANUAL_SOURCE,
  UNPARSED_PARSER_VERSION,
  type IntakeFailureCode,
  type IntakeFailurePoint,
  type IntakeHooks,
  type ManualWbXlsxIntakeResult,
  type ManualWbXlsxMetadata,
  type SourceArtifactManifest,
} from './intake/types.js';
export { calculateCandidates, calculateMargins, normalizeWarehouse, selectTopRisk } from './business-signal/calculate.js';
export { completedSignalWindow, isInsideWindow, moscowWindowBounds } from './business-signal/date-window.js';
export { runBusinessSignal } from './business-signal/pipeline.js';
export { formatStockoutMessage, preflightAndSend, TelegramBotApi } from './business-signal/telegram.js';
export { BusinessSignalError } from './business-signal/types.js';
export {
  makeLineageReference,
  persistLineageReference,
  promoteOrderCounts,
  PromotionError,
  validateStagedRows,
  type LineageReference,
  type PromotionFaultPoint,
  type PromotionHooks,
  type PromotionInput,
  type PromotionResult,
  type PersistLineageInput,
  type QuarantineReason,
} from './facts/promote-order-counts.js';
