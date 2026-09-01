import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { basename, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const CONTRACTS_DIR = join(ROOT, "contracts");
const OUT_DIRS = [
  join(ROOT, "services", "collector", "src", "contracts"),
  join(ROOT, "services", "webapp", "src", "lib", "contracts"),
];

const BANNER =
  "/* eslint-disable */\n// AUTO-GENERATED from contracts/*.schema.json by `make codegen` - DO NOT EDIT.\n";

const files = (await readdir(CONTRACTS_DIR)).filter((f) => f.endsWith(".schema.json"));

if (files.length === 0) {
  console.error("codegen: no *.schema.json found in contracts/");
  process.exit(1);
}

await Promise.all(OUT_DIRS.map((outDir) => mkdir(outDir, { recursive: true })));

const schemasById = new Map();
for (const file of files) {
  const schema = JSON.parse(await readFile(join(CONTRACTS_DIR, file), "utf8"));
  schemasById.set(schema.$id, schema);
}

function inlineLocalRefs(value) {
  if (Array.isArray(value)) {
    return value.map(inlineLocalRefs);
  }
  if (value === null || typeof value !== "object") {
    return value;
  }
  if (typeof value.$ref === "string" && schemasById.has(value.$ref)) {
    return inlineLocalRefs(structuredClone(schemasById.get(value.$ref)));
  }
  return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, inlineLocalRefs(item)]));
}

for (const file of files) {
  const schema = JSON.parse(await readFile(join(CONTRACTS_DIR, file), "utf8"));
  const name = basename(file, ".schema.json");
  const ts = await compile(inlineLocalRefs(schema), name, {
    bannerComment: "",
    style: { singleQuote: true, semi: true },
  });
  for (const outDir of OUT_DIRS) {
    const output = join(outDir, `${name}.ts`);
    await writeFile(output, BANNER + ts, "utf8");
    console.log(`codegen: ${file} -> ${relative(ROOT, output)}`);
  }
}
