import { mkdirSync, readdirSync } from 'node:fs';
import { basename, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const sourceDir = join(root, 'docs', 'architecture');
const outputDir = join(root, 'build', 'architecture');
const executable = join(root, 'node_modules', '.bin', 'mmdc');
const ciPuppeteerConfig = join(root, 'tools', 'puppeteer.ci.json');
const sources = readdirSync(sourceDir).filter((name) => name.endsWith('.mmd')).sort();

if (sources.length !== 4) {
  throw new Error(`expected 4 Mermaid sources, found ${sources.length}`);
}

mkdirSync(outputDir, { recursive: true });
for (const source of sources) {
  const stem = basename(source, '.mmd');
  for (const format of ['svg', 'pdf']) {
    const arguments_ = [
      '--input', join(sourceDir, source),
      '--output', join(outputDir, `${stem}.${format}`),
      '--backgroundColor', 'transparent',
      '--theme', 'neutral',
      '--quiet',
    ];
    if (process.env.CI === 'true') {
      arguments_.push('--puppeteerConfigFile', ciPuppeteerConfig);
    }
    const result = spawnSync(
      executable,
      arguments_,
      { cwd: root, encoding: 'utf-8' },
    );
    if (result.status !== 0) {
      const diagnostic = (result.stderr || result.stdout || 'unknown Mermaid render failure').trim();
      throw new Error(`${source} -> ${format}: ${diagnostic}`);
    }
  }
}

console.log(`rendered ${sources.length} Mermaid sources to SVG and PDF`);
