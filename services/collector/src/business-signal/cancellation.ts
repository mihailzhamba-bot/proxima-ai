import { BusinessSignalError } from './types.js';

export function cancellationError(detail: string): BusinessSignalError {
  return new BusinessSignalError('CANCELLED', detail);
}

function abortReason(signal: AbortSignal): BusinessSignalError {
  return signal.reason instanceof BusinessSignalError ? signal.reason : cancellationError('run cancelled');
}

export function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw abortReason(signal);
}

export async function sleep(milliseconds: number, signal?: AbortSignal): Promise<void> {
  throwIfAborted(signal);
  await new Promise<void>((resolve, reject) => {
    const onAbort = (): void => { clearTimeout(timer); reject(abortReason(signal as AbortSignal)); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve(); }, milliseconds);
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

export async function drainSettled(operations: Iterable<Promise<unknown>>, timeoutMilliseconds: number): Promise<void> {
  let timer: NodeJS.Timeout | undefined;
  try {
    await Promise.race([
      Promise.allSettled(operations),
      new Promise<void>((resolve) => { timer = setTimeout(resolve, timeoutMilliseconds); timer.unref(); }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}
