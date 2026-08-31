#!/usr/bin/env node
/**
 * Turn a stored WB run artifact into an anonymized committed fixture.
 *
 * Thin wrapper around the existing tools/anonymize_fixture.py (Story 1.0):
 * this tool only finds the artifact bytes and chooses the fixture path
 * `services/collector/tests/fixtures/wb-api/<api>/<endpoint>/sample.json`
 * derived from the endpoint registry (AD-4). Anonymization itself stays in
 * the Python tool; nothing here invents response data.
 */
import { spawn } from 'node:child_process';
import { open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { WB_ENDPOINTS, type WbEndpointId } from '../services/collector/src/wb/registry.js';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const FIXTURE_ROOT = resolve(REPO_ROOT, 'services/collector/tests/fixtures/wb-api');
const PYTHON = process.env.PYTHON ?? 'python3';

interface Options {
  artifact: string;
  endpoint: WbEndpointId;
  seed: number;
  saltFile: string;
  limitDays?: number;
  maxBytes?: number;
}

function usage(code: number): never {
  const endpoints = Object.keys(WB_ENDPOINTS).join(', ');
  process.stdout.write(
    [
      'usage: tools/record_fixture.ts --artifact <path-or-sha256> --endpoint <id> --seed 42 \\',
      '       --salt-file <path> [--limit-days N] [--max-bytes N]',
      '',
      `endpoints: ${endpoints}`,
      '',
      'The artifact is a raw WB response (bytes or a hex sha256 of stored bytes);',
      'the output is the anonymized fixture committed for tests.',
    ].join('\n'),
  );
  process.exit(code);
}

function parseArgs(argv: string[]): Options {
  const values: Record<string, string> = {};
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key === '--help' || key === '-h') usage(0);
    const value = argv[index + 1];
    if (!key?.startsWith('--') || !value || value.startsWith('--')) usage(2);
    values[key.slice(2)] = value;
    index += 1;
  }
  const endpoint = values['endpoint'] as WbEndpointId;
  if (!values['artifact'] || !endpoint || !values['seed'] || !values['salt-file']) usage(2);
  if (!(endpoint in WB_ENDPOINTS)) {
    process.stderr.write(`record_fixture: unknown endpoint ${endpoint}; allowed: ${Object.keys(WB_ENDPOINTS).join(', ')}\n`);
    process.exit(2);
  }
  const seed = Number(values['seed']);
  if (!Number.isSafeInteger(seed)) {
    process.stderr.write('record_fixture: --seed must be an integer\n');
    process.exit(2);
  }
  return {
    artifact: values['artifact']!,
    endpoint,
    seed,
    saltFile: values['salt-file']!,
    ...(values['limit-days'] ? { limitDays: Number(values['limit-days']) } : {}),
    ...(values['max-bytes'] ? { maxBytes: Number(values['max-bytes']) } : {}),
  };
}

async function readArtifact(reference: string): Promise<string> {
  const handle = await open(reference, constants.O_RDONLY);
  try {
    return (await handle.readFile()).toString('utf8');
  } finally {
    await handle.close();
  }
}

function runAnonymizer(input: string, output: string, options: Options): Promise<void> {
  const args = [
    'tools/anonymize_fixture.py',
    input,
    output,
    '--seed', String(options.seed),
    '--salt-file', options.saltFile,
    ...(options.limitDays === undefined ? [] : ['--limit-days', String(options.limitDays)]),
    ...(options.maxBytes === undefined ? [] : ['--max-bytes', String(options.maxBytes)]),
  ];
  return new Promise((resolvePromise, reject) => {
    const child = spawn(PYTHON, args, { cwd: REPO_ROOT, stdio: 'inherit' });
    child.on('error', reject);
    child.on('close', (code) => (code === 0 ? resolvePromise() : reject(new Error(`anonymize_fixture.py exited with ${code}`))));
  });
}

async function main(): Promise<void> {
  const options = parseArgs(process.argv.slice(2));
  const spec = WB_ENDPOINTS[options.endpoint];
  const source = resolve(REPO_ROOT, options.artifact);
  const target = resolve(FIXTURE_ROOT, spec.fixtureDir, 'sample.json');
  await runAnonymizer(source, target, options);
  process.stdout.write(`record_fixture: ${spec.fixtureDir}/sample.json updated from ${options.artifact}\n`);
}

main().catch((error: unknown) => {
  process.stderr.write(`record_fixture: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
