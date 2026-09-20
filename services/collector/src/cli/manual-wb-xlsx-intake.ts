#!/usr/bin/env node
import { intakeManualWbXlsx, defaultRepositoryRoot } from '../intake/manual-wb-xlsx.js';
import { IntakeError, type ManualWbXlsxMetadata } from '../intake/types.js';

const REQUIRED = [
  'input',
  'store',
  'tenant',
  'dataset',
  'period-from',
  'period-to',
  'data-as-of',
  'retrieved-at',
  'source-schema-version',
] as const;

type ArgumentName = typeof REQUIRED[number];

function parseArguments(args: string[]): Record<ArgumentName, string> {
  const values = new Map<string, string>();
  for (let index = 0; index < args.length; index += 2) {
    const key = args[index];
    const value = args[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--') || values.has(key.slice(2))) {
      throw new IntakeError('METADATA_INVALID', 'invalid command arguments');
    }
    values.set(key.slice(2), value);
  }
  const result = {} as Record<ArgumentName, string>;
  for (const key of REQUIRED) {
    const value = values.get(key);
    if (!value) throw new IntakeError('METADATA_INVALID', 'required command argument is missing');
    result[key] = value;
  }
  if (values.size !== REQUIRED.length) throw new IntakeError('METADATA_INVALID', 'unsupported command argument');
  return result;
}

async function main(): Promise<void> {
  const args = parseArguments(process.argv.slice(2));
  const metadata: ManualWbXlsxMetadata = {
    tenantId: args.tenant,
    dataset: args.dataset,
    periodFrom: args['period-from'],
    periodTo: args['period-to'],
    dataAsOf: args['data-as-of'],
    retrievedAt: args['retrieved-at'],
    sourceSchemaVersion: args['source-schema-version'],
  };
  const result = await intakeManualWbXlsx({
    inputPath: args.input,
    storeRoot: args.store,
    repositoryRoot: defaultRepositoryRoot(),
    metadata,
  });
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

main().catch((error: unknown) => {
  const code = error instanceof IntakeError ? error.code : 'INTAKE_FAILED';
  process.stderr.write(`${JSON.stringify({ error_code: code })}\n`);
  process.exitCode = 1;
});
