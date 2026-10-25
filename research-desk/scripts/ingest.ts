/**
 * 수집 CLI.
 *   npm run ingest                    전체 출처
 *   npm run ingest -- --source dbt    한 출처
 *   npm run ingest -- --dry-run       임베딩·저장 없이 후보·조각 수만 (키 불필요)
 *   npm run ingest -- --limit 20      maxPages 를 20 으로 덮어씀
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import { parse } from "yaml";
import { getEmbedder, openStore } from "../src/lib/kb";
import { ingestSource } from "../src/lib/kb/ingest";
import type { SourceConfig } from "../src/lib/kb/types";

function arg(name: string): string | undefined {
  const i = process.argv.indexOf(name);
  return i >= 0 ? process.argv[i + 1] : undefined;
}
const flag = (name: string) => process.argv.includes(name);

async function main() {
  const file = path.join(process.cwd(), "kb", "sources.yaml");
  const cfg = parse(await fs.readFile(file, "utf8")) as { sources: SourceConfig[] };
  const only = arg("--source");
  const limit = arg("--limit") ? Number(arg("--limit")) : undefined;
  const dryRun = flag("--dry-run");
  const sources = cfg.sources.filter((s) => !only || s.id === only);
  if (sources.length === 0) throw new Error(`출처를 찾지 못했다: ${only}`);

  const store = await openStore();
  const embedder = dryRun ? null : getEmbedder();
  const rows: string[] = [];
  for (const s of sources) {
    const src = limit ? { ...s, maxPages: limit } : s;
    const t0 = Date.now();
    try {
      const r = await ingestSource(src, store, embedder, { dryRun, log: (l) => console.log(l) });
      rows.push(`${r.sourceId.padEnd(20)} 가져옴 ${String(r.fetched).padStart(4)}  갱신 ${String(r.updated).padStart(4)}  건너뜀 ${String(r.skipped).padStart(4)}  조각 ${String(r.chunks).padStart(5)}  ${((Date.now() - t0) / 1000).toFixed(1)}s`);
    } catch (e) {
      rows.push(`${s.id.padEnd(20)} 실패: ${(e as Error).message}`);
    }
  }
  await store.close();
  console.log("\n" + rows.join("\n"));
  if (dryRun) console.log("\n(dry-run: 임베딩·저장 안 함)");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
