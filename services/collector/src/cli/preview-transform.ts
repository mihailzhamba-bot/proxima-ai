#!/usr/bin/env node
import { readPrivateSecret } from '../business-signal/secrets.js';
import { privateDatabasePool } from '../business-signal/runtime.js';
import { PreviewTransformError, transformStagingToPreview } from '../staging/preview-transform.js';

const REQUIRED = ['database-url-file', 'tenant', 'task-id'] as const;

type ArgumentName = typeof REQUIRED[number];

function parseArguments(args: string[]): Record<ArgumentName, string> {
  const values = new Map<string, string>();
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    const value = args[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--') || values.has(key.slice(2))) {
      throw new PreviewTransformError('TRANSFORM_FAILED', 'invalid command arguments');
    }
    values.set(key.slice(2), value);
  }
  const result = {} as Record<ArgumentName, string>;
  for (const key of REQUIRED) {
    const value = values.get(key);
    if (!value) throw new PreviewTransformError('TRANSFORM_FAILED', 'required command argument is missing');
    result[key] = value;
  }
  if (values.size !== REQUIRED.length) throw new PreviewTransformError('TRANSFORM_FAILED', 'unsupported command argument');
  return result;
}

async function main(): Promise<void> {
  const args = parseArguments(process.argv.slice(2));
  const pool = await privateDatabasePool(args['database-url-file']);
  try {
    const result = await transformStagingToPreview(pool, {
      tenantId: args.tenant,
      taskId: args['task-id'],
    });
    process.stdout.write(`${JSON.stringify(result)}\n`);
  } finally {
    await pool.end();
  }
}

main().catch((error: unknown) => {
  const code = error instanceof PreviewTransformError ? error.code : 'TRANSFORM_FAILED';
  process.stderr.write(`${JSON.stringify({ error_code: code })}\n`);
  process.exitCode = 1;
});
