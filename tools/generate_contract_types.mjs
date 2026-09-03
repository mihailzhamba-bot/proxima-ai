import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const CONTRACTS_DIR = join(ROOT, "contracts");
const TARGETS = [
  ["services", "collector", "src", "contracts"],
  ["services", "webapp", "src", "lib", "contracts"],
];

const BANNER =
  "/* eslint-disable */\n// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.\n";

const files = (await readdir(CONTRACTS_DIR)).filter((f) => f.endsWith(".schema.json"));

if (files.length === 0) {
  console.error("codegen: no *.schema.json found in contracts/");
  process.exit(1);
}

for (const target of TARGETS) {
  await mkdir(join(ROOT, ...target), { recursive: true });
}

for (const file of files) {
  const schema = JSON.parse(await readFile(join(CONTRACTS_DIR, file), "utf8"));
  const name = basename(file, ".schema.json");
  const ts = await compile(schema, name, {
    bannerComment: "",
    cwd: CONTRACTS_DIR,
    style: { singleQuote: true, semi: true },
  });
  for (const target of TARGETS) {
    await writeFile(join(ROOT, ...target, `${name}.ts`), BANNER + ts + "\n", "utf8");
    console.log(`codegen: ${file} -> ${target.join("/")}/${name}.ts`);
  }
}

