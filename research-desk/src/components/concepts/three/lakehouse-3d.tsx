"use client";

/**
 * 3D 레이크하우스 스택 — 이 개념은 말 그대로 "층"이다. 평면 목록보다 쌓인 판이 정직하다.
 * 층을 누르면 그 판이 앞으로 빠져나오고 나머지는 물러난다.
 */
import { Grid, Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { LAKE_LAYERS, LAKE_NOTE } from "@/lib/concepts/lakehouse";
import { STAGE_BG, Stage } from "./stage";
import { C, labelStyle, prefersReducedMotion } from "./theme";

const SLAB_W = 9.4;
const SLAB_D = 5.6;
const SLAB_H = 0.55;
const GAP = 1.0;
/** 위에서 아래로 갈수록 한 단계씩 어두워지는 돌색 — 층의 깊이를 색으로 보여준다. */
const REST_TINT = ["#6a563e", "#5e4c37", "#524230", "#463829", "#3b2f23"];

function Slab({
  index,
  total,
  label,
  items,
  active,
  onSelect,
}: {
  index: number;
  total: number;
  label: string;
  items: string;
  active: boolean;
  onSelect: () => void;
}) {
  const ref = useRef<THREE.Group>(null);
  const [hover, setHover] = useState(false);
  const box = useMemo(() => new THREE.BoxGeometry(SLAB_W, SLAB_H, SLAB_D), []);
  // index 0 이 맨 위(쿼리 엔진), 마지막이 바닥(객체 스토리지)
  const baseY = (total - 1 - index) * (SLAB_H + GAP) - ((total - 1) * (SLAB_H + GAP)) / 2;
  const targetZ = active ? 1.5 : 0;
  const targetScale = active ? 1.05 : 1;

  useFrame((_, delta) => {
    const g = ref.current;
    if (!g) return;
    const k = Math.min(1, delta * 6);
    g.position.z += (targetZ - g.position.z) * k;
    const s = g.scale.x + (targetScale - g.scale.x) * k;
    g.scale.setScalar(s);
  });

  return (
    <group ref={ref} position={[0, baseY, 0]}>
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          setHover(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHover(false);
          document.body.style.cursor = "";
        }}
      >
        <boxGeometry args={[SLAB_W, SLAB_H, SLAB_D]} />
        {/* 금속도를 높이면 어두운 스테이지를 그대로 비춰 판이 새까맣게 죽는다.
            쉬지 않는 층도 보여야 "쌓임"이 읽히므로, 거친 돌에 가깝게 두고 깊이에 따라 조금씩 어둡게 한다. */}
        <meshStandardMaterial
          color={active ? C.accent : hover ? "#7a6248" : REST_TINT[index % REST_TINT.length]}
          emissive={active ? C.accent : "#1a120a"}
          emissiveIntensity={active ? 0.22 : 0.35}
          roughness={active ? 0.4 : 0.62}
          metalness={active ? 0.45 : 0.22}
        />
      </mesh>
      <lineSegments>
        <edgesGeometry args={[box]} />
        <lineBasicMaterial color={active ? C.accentBright : "#8a6f4c"} />
      </lineSegments>
      <Html position={[SLAB_W / 2 + 0.4, 0, SLAB_D / 2 - 0.4]} center={false} distanceFactor={12} zIndexRange={[20, 0]} style={labelStyle}>
        <span style={{ display: "inline-block", transform: "translateY(-50%)", opacity: active ? 1 : 0.8, lineHeight: 1.35 }}>
          <span style={{ fontSize: 15.5, color: active ? C.accentBright : "#f0e8db" }}>{label}</span>
          <br />
          <span style={{ fontSize: 11, color: active ? "#b4a893" : "#8b8175" }}>{items}</span>
        </span>
      </Html>
    </group>
  );
}

export function Lakehouse3D({ focus }: { focus?: string }) {
  const [sel, setSel] = useState(focus && LAKE_LAYERS.some((l) => l.id === focus) ? focus : "format");
  const cur = LAKE_LAYERS.find((l) => l.id === sel)!;
  const reduced = useMemo(() => prefersReducedMotion(), []);

  return (
    <div>
      <div className="overflow-hidden rounded-xl border border-line" style={{ height: 470, background: STAGE_BG }} aria-label="3D 레이크하우스 층 장면">
        <Canvas dpr={[1, 1.8]} camera={{ position: [-1.2, 5.4, 20], fov: 36 }} gl={{ antialias: false, alpha: true }}>
          <Stage bloom={1.05}>
          <Grid
            position={[0, -5.6, 0]}
            args={[60, 40]}
            cellSize={1.4}
            cellThickness={0.5}
            cellColor="#2b241c"
            sectionSize={7}
            sectionThickness={0.9}
            sectionColor="#5c4630"
            fadeDistance={54}
            fadeStrength={1.4}
            infiniteGrid
          />
          {LAKE_LAYERS.map((l, i) => (
            <Slab
              key={l.id}
              index={i}
              total={LAKE_LAYERS.length}
              label={l.label}
              items={l.items}
              active={l.id === sel}
              onSelect={() => setSel(l.id)}
            />
          ))}
          <OrbitControls
            target={[2.6, -0.2, 0]}
            enablePan={false}
            enableDamping
            dampingFactor={0.08}
            minDistance={13}
            maxDistance={32}
            minPolarAngle={Math.PI * 0.22}
            maxPolarAngle={Math.PI * 0.52}
            autoRotate={!reduced}
            autoRotateSpeed={0.35}
          />
          </Stage>
        </Canvas>
      </div>
      <div className="mt-3 rounded border border-line p-3 text-sm">
        <p className="text-xs uppercase tracking-widest text-faint">이 층이 하는 일</p>
        <p className="mt-1 text-ink">{cur.label}</p>
        <p className="mt-1 text-dim">{cur.role}</p>
        <p className="mt-3 text-xs text-faint">{LAKE_NOTE}</p>
      </div>
    </div>
  );
}
