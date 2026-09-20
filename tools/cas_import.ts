#!/usr/bin/env node
import { importCasArtifact, type CasArtifactSource } from '../services/collector/src/wb/cas-artifact.js';

function value(argv: readonly string[], option: string): string {
  const index = argv.indexOf(option);
  if (index < 0 || !argv[index + 1] || argv[index + 1]!.startsWith('--')) throw new Error(`required option: ${option}`);
  return argv[index + 1]!;
}

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  const file = argv[0];
  if (!file || file.startsWith('--')) throw new Error('usage: cas_import.ts <file> --retrieved-at <ISO> --source official_wb_statistics');
  const source = value(argv, '--source');
  if (source !== 'official_wb_statistics') throw new Error('--source must be official_wb_statistics');
  const rawRoot = process.env.PROXIMA_RAW_DIR;
  if (!rawRoot) throw new Error('PROXIMA_RAW_DIR is not set');
  const manifest = await importCasArtifact({ file, rawRoot, repositoryRoot: process.cwd(), retrievedAt: new Date(value(argv, '--retrieved-at')), source: source as CasArtifactSource });
  process.stdout.write(`${JSON.stringify({ content_sha256: manifest.content_sha256, object_locator: manifest.object_locator, retrieved_at: manifest.retrieved_at })}\n`);
}

main().catch((error: unknown) => { process.stderr.write(`cas_import: ${error instanceof Error ? error.message : String(error)}\n`); process.exit(1); });
