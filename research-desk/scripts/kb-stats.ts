import { openStore } from "../src/lib/kb";

openStore()
  .then(async (s) => {
    const st = await s.stats();
    console.log(`문서 ${st.docs} · 조각 ${st.chunks}`);
    for (const x of st.sources) console.log(`  ${x.sourceId.padEnd(20)} 문서 ${String(x.docs).padStart(4)}  조각 ${String(x.chunks).padStart(5)}  최근 ${x.lastFetchedAt ?? "-"}`);
    await s.close();
  })
  .catch((e) => {
    console.error(e);
    process.exit(1);
  });
