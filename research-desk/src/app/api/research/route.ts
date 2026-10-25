/**
 * POST /api/research  { type, topic, geography?, timeframe?, context? }  (옛 { question } 도 topic 으로 받는다)
 * → text/event-stream. 파이프라인 이벤트를 한 줄씩 흘려보낸다.
 *
 * 키는 서버 환경변수 ANTHROPIC_API_KEY 에서만 읽는다. 브라우저로 나가지 않는다.
 */
import { createAnthropicLlm } from "@/lib/research/llm";
import { normalizeBrief, runResearch } from "@/lib/research/pipeline";
import { encodeEvent } from "@/lib/research/sse";
import type { ResearchEvent } from "@/lib/research/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
// Vercel 함수 상한. 조사 4~5건 병렬 + 반증 + 집필이면 수 분이 걸릴 수 있다.
export const maxDuration = 300;

const MAX_TOPIC_CHARS = 2000;
const MAX_FIELD_CHARS = 1000;

function envInt(name: string, fallback: number): number {
  const v = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "JSON 본문이 필요하다." }, { status: 400 });
  }
  const brief = normalizeBrief(body);
  if (!brief) return Response.json({ error: "topic 이 비어 있다." }, { status: 400 });
  if (brief.topic.length > MAX_TOPIC_CHARS) {
    return Response.json({ error: `topic 은 ${MAX_TOPIC_CHARS}자 이하여야 한다.` }, { status: 400 });
  }
  if ([brief.geography, brief.timeframe, brief.context].some((f) => f.length > MAX_FIELD_CHARS)) {
    return Response.json({ error: `지역·기간·배경은 각각 ${MAX_FIELD_CHARS}자 이하여야 한다.` }, { status: 400 });
  }
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    return Response.json({ error: "서버에 ANTHROPIC_API_KEY 가 없다. .env.local 을 확인하라." }, { status: 500 });
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;
      const emit = (ev: ResearchEvent) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(encodeEvent(ev)));
        } catch {
          closed = true;
        }
      };
      try {
        await runResearch(brief, createAnthropicLlm(), emit, {
          maxSearches: envInt("RESEARCH_MAX_SEARCHES", 6),
        });
      } catch (err) {
        emit({ type: "error", message: err instanceof Error ? err.message : String(err) });
      } finally {
        closed = true;
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
