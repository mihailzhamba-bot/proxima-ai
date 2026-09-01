#!/usr/bin/env node
/**
 * Collect one WB endpoint through the single WB client (Story 1.1).
 *
 * Tokens are read from files passed as --<category>-token-file, following
 * src/cli/stockout-signal.ts. The endpoint must be a registry key; no URL is
 * ever accepted from the command line. Live network stays fail-closed unless
 * WB_ALLOW_LIVE_NETWORK=1 (AD-4).
 */
import { WbClient, WbClientError, type WbResponseRecord } from '../wb/client.js';
import { networkTransport, type WbTransport } from '../wb/transport.js';
import { WB_ENDPOINTS, type WbEndpointId, type WbTokenCategory } from '../wb/registry.js';
import { readPrivateSecret } from '../business-signal/secrets.js';

export interface WbCollectArgs {
  endpoint: WbEndpointId;
  tokenFiles: Partial<Record<WbTokenCategory, string>>;
}

export interface WbCollectResult {
  endpoint: WbEndpointId;
  status: number;
  bytes: number;
  url: string;
}

export function parseWbCollectArgs(argv: readonly string[]): WbCollectArgs {
  const tokenFiles: Partial<Record<WbTokenCategory, string>> = {};
  let endpoint: string | undefined;
  for (let index = 0; index < argv.length; index += 1) {
    const key = argv[index];
    if (key !== '--endpoint' && key !== '--statistics-token-file' && key !== '--analytics-token-file') {
      throw new Error(`unknown option ${String(key)}; expected --endpoint, --statistics-token-file, --analytics-token-file`);
    }
    const value = argv[index + 1];
    if (!value || value.startsWith('--')) throw new Error(`option ${key} requires a value`);
    index += 1;
    if (key === '--endpoint') endpoint = value;
    else tokenFiles[key === '--statistics-token-file' ? 'statistics' : 'analytics'] = value;
  }
  if (!endpoint) throw new Error('required option: --endpoint <registry key>');
  if (!(endpoint in WB_ENDPOINTS)) {
    throw new Error(`unknown endpoint ${endpoint}; allowed: ${Object.keys(WB_ENDPOINTS).join(', ')}`);
  }
  const required = WB_ENDPOINTS[endpoint as WbEndpointId].token;
  if (!tokenFiles[required]) {
    throw new Error(`endpoint ${endpoint} requires --${required}-token-file`);
  }
  return { endpoint: endpoint as WbEndpointId, tokenFiles };
}

export async function runWbCollect(
  args: WbCollectArgs,
  tokens: Readonly<Partial<Record<WbTokenCategory, string>>>,
  options: { transport?: WbTransport } = {},
): Promise<WbCollectResult> {
  const client = new WbClient(tokens, options.transport ? { transport: options.transport } : {});
  const record: WbResponseRecord = await client.request(args.endpoint);
  return { endpoint: record.endpointId, status: record.httpStatus, bytes: record.body.length, url: record.requestUrl };
}

async function main(): Promise<void> {
  const args = parseWbCollectArgs(process.argv.slice(2));
  const tokens: Partial<Record<WbTokenCategory, string>> = {};
  for (const [category, file] of Object.entries(args.tokenFiles) as [WbTokenCategory, string][]) {
    tokens[category] = await readPrivateSecret(file, `WB ${category} token file`);
  }
  const result = await runWbCollect(args, tokens);
  process.stdout.write(`${JSON.stringify(result)}\n`);
}

if (process.argv[1] && process.argv[1].endsWith('wb-collect.ts')) {
  main().catch((error: unknown) => {
    const code = error instanceof WbClientError ? error.code : 'WB_COLLECT_FAILED';
    process.stderr.write(`wb-collect: ${code}: ${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  });
}
