"use client";

/**
 * 공통 무대 — 세 장면이 같은 빛과 후처리를 쓴다.
 *
 * 어두운 배경에 무광 재질만 놓으면 형태가 뭉개진다. 그래서 세 가지를 얹는다.
 *   1) 환경광(Lightformer 3개) — 따뜻한 키 + 차가운 림. 금속 표면에 그라데이션이 생겨 입체가 산다.
 *   2) Bloom — 발광하는 브론즈가 실제로 빛나 보인다. 이 장면들의 "예쁨"은 대부분 여기서 온다.
 *   3) Vignette — 가장자리를 눌러 시선을 가운데로 모은다.
 * 배경은 캔버스가 아니라 컨테이너의 CSS 그라데이션이다 (캔버스는 투명).
 */
import { Environment, Lightformer } from "@react-three/drei";
import { Bloom, EffectComposer, Vignette } from "@react-three/postprocessing";
import type { ReactNode } from "react";

/** 장면 컨테이너 배경 — 위쪽이 살짝 밝은 무대 조명. */
export const STAGE_BG = "radial-gradient(120% 90% at 50% -10%, #221c16 0%, #14100d 42%, #0a0908 100%)";

export function Stage({ children, bloom = 1.15 }: { children: ReactNode; bloom?: number }) {
  return (
    <>
      <Environment resolution={256} frames={1}>
        <Lightformer form="rect" intensity={3.2} color="#ffd9a8" position={[0, 7, 9]} scale={[14, 7, 1]} />
        <Lightformer form="rect" intensity={1.6} color="#8fa8ff" position={[-11, 3, -7]} scale={[11, 7, 1]} rotation={[0, Math.PI / 3, 0]} />
        <Lightformer form="rect" intensity={1.3} color="#ffab6b" position={[11, -2, -7]} scale={[11, 7, 1]} rotation={[0, -Math.PI / 3, 0]} />
        <Lightformer form="circle" intensity={2.0} color="#ffffff" position={[0, 12, 0]} scale={6} rotation={[-Math.PI / 2, 0, 0]} />
      </Environment>
      <ambientLight intensity={0.28} />
      <directionalLight position={[7, 13, 11]} intensity={1.0} color="#fff1dd" />
      {children}
      <EffectComposer multisampling={4}>
        <Bloom mipmapBlur luminanceThreshold={0.22} luminanceSmoothing={0.3} intensity={bloom} radius={0.72} />
        <Vignette offset={0.3} darkness={0.75} />
      </EffectComposer>
    </>
  );
}
