/**
 * POST /api/ask { question } → text/event-stream (AskEvent)
 */
import { getEmbedder, getReranker, kbConfigured, openStore } from "@/lib/kb";
import { askKb } from "@/lib/kb/answer";
import type { AskEvent } from "@/lib/kb/types";
import { encodeEvent } from "@/lib/research/sse";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 120;

const MAX_CHARS = 1000;

export async function POST(req: Request): Promise<Response> {
  let question = "";
  try {
    const body = (await req.json()) as { question?: unknown };
    question = typeof body.question === "string" ? body.question.trim() : "";
  } catch {
    return Response.json({ error: "JSON 본문이 필요하다." }, { status: 400 });
  }
  if (!question) return Response.json({ error: "question 이 비어 있다." }, { status: 400 });
  if (question.length > MAX_CHARS) return Response.json({ error: `question 은 ${MAX_CHARS}자 이하여야 한다.` }, { status: 400 });
  const cfg = kbConfigured();
  if (!cfg.ok) return Response.json({ error: `서버 환경변수가 없다: ${cfg.missing.join(", ")}` }, { status: 500 });

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      const emit = (ev: AskEvent) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(encodeEvent(ev)));
        } catch {
          closed = true;
        }
      };
      try {
        const store = await openStore();
        await askKb(question, { embedder: getEmbedder(), store, reranker: getReranker() }, emit);
      } catch (err) {
        emit({ type: "error", message: err instanceof Error ? err.message : String(err) });
      } finally {
        closed = true;
        controller.close();
      }
    },
  });
  return new Response(stream, {
    headers: { "Content-Type": "text/event-stream; charset=utf-8", "Cache-Control": "no-cache, no-transform", Connection: "keep-alive", "X-Accel-Buffering": "no" },
  });
}
