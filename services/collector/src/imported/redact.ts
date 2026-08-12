const SENSITIVE_KEY = /^(?:cookie|authorization|token|csrf|xsrf|auth|session|api[-_]?key|password|secret|credentials?|email|client[-_]?id|user(?:name)?|name)$/i;
const EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
const BEARER = /\b(Bearer\s+)[A-Za-z0-9._~+/=-]+/gi;
const LONG_SECRET = /\b[A-Za-z0-9+/=_-]{40,}\b/g;
const SENSITIVE_ASSIGNMENT = /\b(token|password|secret|credentials?|user(?:name)?|name|email|authorization|cookie|session|client[-_]?id|api[-_]?key)\b(\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;&]+)/gi;
const URL_IN_TEXT = /https?:\/\/[^\s<>"']+/gi;

export function sanitizeUrl(raw: string): string {
  try {
    const url = new URL(raw);
    url.username = '';
    url.password = '';
    url.search = '';
    url.hash = '';
    return url.toString();
  } catch {
    return redactScalar(raw.replace(/[?#].*$/, ''));
  }
}

function redactScalar(value: string): string {
  return value
    .replace(SENSITIVE_ASSIGNMENT, '$1$2<REDACTED>')
    .replace(EMAIL, '<REDACTED_EMAIL>')
    .replace(BEARER, '$1<REDACTED>')
    .replace(LONG_SECRET, '<REDACTED>');
}

export function redactString(value: string): string {
  return redactScalar(value.replace(URL_IN_TEXT, (url) => sanitizeUrl(url)));
}

export function redactValue(value: unknown, key = ''): unknown {
  if (SENSITIVE_KEY.test(key)) return '<REDACTED>';
  if (typeof value === 'string') {
    if (/^https?:\/\//i.test(value)) return sanitizeUrl(value);
    return redactString(value);
  }
  if (Array.isArray(value)) return value.map((item) => redactValue(item));
  if (typeof value === 'object' && value !== null) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([childKey, childValue]) => [
        childKey,
        redactValue(childValue, childKey),
      ]),
    );
  }
  return value;
}

export interface ErrorDiagnostic {
  error_type: string;
  error_code?: string;
  message: string;
  http_status?: number;
  retryable?: boolean;
  secondary?: ErrorDiagnostic[];
}

export function errorDiagnostic(error: unknown): ErrorDiagnostic {
  if (!(error instanceof Error)) return { error_type: 'UnknownError', message: 'Unknown failure' };
  const source = error as Error & {
    code?: unknown;
    trpcCode?: unknown;
    httpStatus?: unknown;
    retryable?: unknown;
    kind?: unknown;
    secondaryErrors?: unknown;
  };
  const candidateCode = typeof source.code === 'string'
    ? source.code
    : typeof source.trpcCode === 'string' ? source.trpcCode : undefined;
  const safeCode = candidateCode && /^[A-Z][A-Z0-9_]{0,63}$/.test(candidateCode) ? candidateCode : undefined;
  return {
    error_type: source.name,
    ...(safeCode ? { error_code: safeCode } : {}),
    message: redactString(error.message).slice(0, 500),
    ...(typeof source.httpStatus === 'number' ? { http_status: source.httpStatus } : {}),
    ...(typeof source.retryable === 'boolean' ? { retryable: source.retryable } : {}),
    ...(Array.isArray(source.secondaryErrors)
      ? { secondary: source.secondaryErrors.slice(0, 5).map((secondary) => errorDiagnostic(secondary)) }
      : {}),
  };
}
