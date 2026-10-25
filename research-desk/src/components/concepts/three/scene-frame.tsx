"use client";

/**
 * 3D 씬 액자 — WebGL 확인, 2D 되돌리기 토글, 지연 로딩.
 * three.js 는 이 파일에서만 동적으로 불러온다 (서버 렌더 제외, 다른 페이지 번들에 안 섞임).
 */
import dynamic from "next/dynamic";
import { useSyncExternalStore, type ReactNode } from "react";
import { getServerSnapshot, getSnapshot, isPlaceholder, setWant, subscribe } from "./view-pref";

export type SceneKind = "pipeline" | "lakehouse" | "galaxy";

function Loading({ height }: { height: number }) {
  return (
    <div className="flex items-center justify-center rounded-lg border border-line bg-bg text-xs text-faint" style={{ height }}>
      3D 장면을 준비하는 중…
    </div>
  );
}

const Pipeline3D = dynamic(() => import("./pipeline-3d").then((m) => m.Pipeline3D), { ssr: false, loading: () => <Loading height={520} /> });
const Lakehouse3D = dynamic(() => import("./lakehouse-3d").then((m) => m.Lakehouse3D), { ssr: false, loading: () => <Loading height={460} /> });
const Galaxy3D = dynamic(() => import("./galaxy-3d").then((m) => m.Galaxy3D), { ssr: false, loading: () => <Loading height={520} /> });

interface Props {
  kind: SceneKind;
  /** 3D 를 못 쓰거나 유저가 껐을 때 보여줄 평면 버전. */
  flat: ReactNode;
  /** 3D 씬에 넘길 값. */
  mode?: "lineage" | "incident";
  initial?: string;
  focus?: string;
  label: string;
}

export function Scene3D({ kind, flat, mode, initial, focus, label }: Props) {
  const pref = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const ready = !isPlaceholder(pref);
  const on = pref.supported && pref.want;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs">
        <span className="text-faint">{label}</span>
        <div className="ml-auto flex overflow-hidden rounded border border-line" role="group" aria-label="보기 전환">
          <button
            type="button"
            onClick={() => setWant(true)}
            disabled={ready && !pref.supported}
            aria-pressed={on}
            className={`px-2 py-0.5 ${on ? "bg-accent text-bg" : "text-dim hover:text-ink"} disabled:opacity-40`}
          >
            입체
          </button>
          <button type="button" onClick={() => setWant(false)} aria-pressed={!on} className={`px-2 py-0.5 ${!on ? "bg-accent text-bg" : "text-dim hover:text-ink"}`}>
            평면
          </button>
        </div>
      </div>
      {ready && !pref.supported && <p className="mb-2 text-xs text-open">이 브라우저에서 WebGL 을 쓸 수 없어 평면으로 보여준다.</p>}
      {!on ? (
        flat
      ) : kind === "pipeline" ? (
        <Pipeline3D mode={mode ?? "lineage"} initial={initial} />
      ) : kind === "lakehouse" ? (
        <Lakehouse3D focus={focus} />
      ) : (
        <Galaxy3D focus={focus} />
      )}
    </div>
  );
}
