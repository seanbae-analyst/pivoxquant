import { kbConfigured, openStore } from "@/lib/kb";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const store = await openStore();
    const stats = await store.stats();
    return Response.json({ ok: true, configured: kbConfigured(), backend: process.env.DATABASE_URL ? "postgres" : "file", ...stats });
  } catch (err) {
    return Response.json({ ok: false, error: err instanceof Error ? err.message : String(err) }, { status: 500 });
  }
}
