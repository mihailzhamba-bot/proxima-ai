export class AuthRequiredError extends Error {
  readonly code = 'AUTH_REQUIRED';
  readonly secondaryErrors: Error[] = [];

  constructor(message: string) {
    super(message);
    this.name = 'AuthRequiredError';
  }
}

export function attachSecondaryError(primary: unknown, secondary: unknown): void {
  if (!(primary instanceof Error) || !(secondary instanceof Error)) return;
  const target = primary as Error & { secondaryErrors?: Error[] };
  if (!Array.isArray(target.secondaryErrors)) {
    Object.defineProperty(target, 'secondaryErrors', { value: [], enumerable: false, writable: false });
  }
  target.secondaryErrors!.push(secondary);
}

export function isAuthRequiredError(error: unknown): error is AuthRequiredError {
  return error instanceof AuthRequiredError;
}

export function isLoginUrl(value: string | undefined): boolean {
  if (!value) return false;
  try {
    const path = new URL(value).pathname.toLowerCase();
    return /(^|\/)(login|signin|auth)(\/|$)/.test(path);
  } catch {
    return /(^|\/)(login|signin|auth)(\/|$)/i.test(value);
  }
}
