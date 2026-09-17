"use client";

/**
 * 3D 개념 별자리 — 여섯 영역이 원을 따라 서고, 개념이 그 위아래로 뜬다.
 * 관계선은 가운데를 향해 휘어 서로를 비켜 간다. 멀리 있는 이름은 흐려져 깊이가 읽힌다.
 * 노드를 누르면 개념 페이지로 간다.
 */
import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { AREAS, CONCEPTS, conceptBySlug, conceptsInArea, edges } from "@/lib/concepts/concepts";
import { AREA_TINT, C, labelStyle, prefersReducedMotion } from "./theme";

const R = 11;
const Y_STEP = 3.4;

function positions(): Map<string, THREE.Vector3> {
  const out = new Map<string, THREE.Vector3>();
  AREAS.forEach((a, i) => {
    const ang = (i / AREAS.length) * Math.PI * 2 - Math.PI / 2;
    const list = conceptsInArea(a.id);
    list.forEach((c, j) => {
      const r = R + (j % 2 === 0 ? 0 : 2.1);
      const y = (j - (list.length - 1) / 2) * Y_STEP;
      out.set(c.slug, new THREE.Vector3(Math.cos(ang) * r, y, Math.sin(ang) * r));
    });
  });
  return out;
}

const tmp = new THREE.Vector3();

function Node({
  slug,
  name,
  pos,
  tint,
  state,
  onHover,
  onLeave,
}: {
  slug: string;
  name: string;
  pos: THREE.Vector3;
  tint: string;
  state: "focus" | "linked" | "idle";
  onHover: () => void;
  onLeave: () => void;
}) {
  const router = useRouter();
  const mesh = useRef<THREE.Mesh>(null);
  const label = useRef<HTMLSpanElement>(null);
  const focus = state === "focus";
  const linked = state === "linked";

  useFrame((s) => {
    const m = mesh.current;
    if (!m) return;
    const target = focus ? 1.45 : linked ? 1.15 : 1;
    m.scale.setScalar(m.scale.x + (target - m.scale.x) * 0.15);
    m.rotation.y = s.clock.elapsedTime * 0.2 + pos.x;
    // 깊이 단서 — 카메라에서 먼 이름은 흐려진다. 평면 지도에는 없는 정보.
    if (label.current) {
      const d = s.camera.position.distanceTo(m.getWorldPosition(tmp));
      const near = THREE.MathUtils.clamp(THREE.MathUtils.mapLinear(d, 20, 44, 1, 0.38), 0.38, 1);
      label.current.style.opacity = String(focus || linked ? Math.max(0.85, near) : near);
    }
  });

  return (
    <group position={pos}>
      <mesh
        ref={mesh}
        onClick={(e) => {
          e.stopPropagation();
          router.push(`/concepts/${slug}`);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          onLeave();
          document.body.style.cursor = "";
        }}
      >
        <icosahedronGeometry args={[0.72, 0]} />
        <meshStandardMaterial
          color={focus ? C.accent : tint}
          emissive={focus ? C.accent : tint}
          emissiveIntensity={focus ? 1.1 : linked ? 0.5 : 0.22}
          roughness={0.35}
          metalness={0.5}
          flatShading
        />
      </mesh>
      <Html position={[0, -1.25, 0]} center distanceFactor={16} zIndexRange={[20, 0]} style={labelStyle}>
        <span ref={label} style={{ fontSize: 13, color: focus ? C.accent : C.ink, fontWeight: focus ? 600 : 400 }}>
          {name}
        </span>
      </Html>
    </group>
  );
}

function Scene({ focus, hover, setHover }: { focus?: string; hover: string | null; setHover: (s: string | null) => void }) {
  const pos = useMemo(() => positions(), []);
  const reduced = useMemo(() => prefersReducedMotion(), []);
  const active = hover ?? focus ?? null;
  const activeC = active ? conceptBySlug(active) : null;
  const linked = useMemo(() => new Set(activeC ? activeC.neighbors.map((n) => n.slug) : []), [activeC]);

  const curves = useMemo(
    () =>
      edges().map(([a, b]) => {
        const pa = pos.get(a)!;
        const pb = pos.get(b)!;
        const mid = pa.clone().add(pb).multiplyScalar(0.5).multiplyScalar(0.4);
        return { key: `${a}|${b}`, a, b, curve: new THREE.QuadraticBezierCurve3(pa, mid, pb) };
      }),
    [pos],
  );

  const group = useRef<THREE.Group>(null);
  useFrame((_, delta) => {
    if (reduced || hover) return;
    if (group.current) group.current.rotation.y += delta * 0.05;
  });

  return (
    <>
      <color attach="background" args={[C.bg]} />
      <fog attach="fog" args={[C.bg, 26, 62]} />
      <ambientLight intensity={0.95} />
      <directionalLight position={[8, 14, 12]} intensity={0.9} color={C.ink} />
      <pointLight position={[0, 0, 0]} intensity={140} distance={34} color={C.accent} />
      <pointLight position={[0, 10, 22]} intensity={90} distance={50} color={C.ink} />
      <group ref={group}>
        {[R, R + 2.1].map((r) => (
          <mesh key={r} rotation={[Math.PI / 2, 0, 0]}>
            <torusGeometry args={[r, 0.012, 6, 128]} />
            <meshBasicMaterial color="#39332c" toneMapped={false} />
          </mesh>
        ))}
        {curves.map((e) => {
          const on = !!activeC && (e.a === activeC.slug || e.b === activeC.slug);
          return (
            <mesh key={e.key}>
              <tubeGeometry args={[e.curve, 36, on ? 0.055 : 0.026, 6, false]} />
              <meshStandardMaterial
                color={on ? C.accent : "#4a4238"}
                emissive={on ? C.accent : "#000000"}
                emissiveIntensity={on ? 1.3 : 0}
                transparent
                opacity={on ? 1 : 0.75}
                toneMapped={false}
              />
            </mesh>
          );
        })}
        {CONCEPTS.map((c) => (
          <Node
            key={c.slug}
            slug={c.slug}
            name={c.name}
            pos={pos.get(c.slug)!}
            tint={AREA_TINT[c.area]}
            state={c.slug === active ? "focus" : linked.has(c.slug) ? "linked" : "idle"}
            onHover={() => setHover(c.slug)}
            onLeave={() => setHover(null)}
          />
        ))}
      </group>
      <OrbitControls enablePan={false} enableDamping dampingFactor={0.08} minDistance={18} maxDistance={44} minPolarAngle={Math.PI * 0.18} maxPolarAngle={Math.PI * 0.7} />
    </>
  );
}

export function Galaxy3D({ focus }: { focus?: string }) {
  const [hover, setHover] = useState<string | null>(null);
  const shownSlug = hover ?? focus ?? null;
  const shown = shownSlug ? conceptBySlug(shownSlug) : null;
  const area = shown ? AREAS.find((a) => a.id === shown.area) : null;

  return (
    <div>
      <div className="overflow-hidden rounded-lg border border-line" style={{ height: 520 }} aria-label="3D 개념 별자리 장면">
        <Canvas dpr={[1, 1.8]} camera={{ position: [0, 6.5, 26], fov: 40 }} gl={{ antialias: true }}>
          <Scene focus={focus} hover={hover} setHover={setHover} />
        </Canvas>
      </div>
      <p className="mt-2 min-h-10 text-xs text-dim">
        {shown ? (
          <>
            <span className="text-faint">{area?.label} · </span>
            <span className="text-ink">{shown.name}</span> — {shown.definition}
          </>
        ) : (
          "끌면 별자리가 돌아간다. 노드에 올리면 정의가, 누르면 개념 페이지가 열린다. 여섯 무리가 각각 한 영역이다."
        )}
      </p>
      <ul className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-faint">
        {AREAS.map((a) => (
          <li key={a.id} className="flex items-center gap-1.5">
            <span aria-hidden className="inline-block h-2 w-2 rounded-full" style={{ background: AREA_TINT[a.id] }} />
            {a.label} <span className="text-dim">{conceptsInArea(a.id).length}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
