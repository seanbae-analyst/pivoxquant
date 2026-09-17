"use client";

/**
 * 3D 데이터 파이프라인 — 앵커 데이터셋을 깊이 있는 공간에 세운다.
 *
 * 왜 3D 여야 하나: 리니지는 본래 겹치는 그래프다. 평면에서는 선이 서로를 가리지만,
 * 깊이가 생기면 상류에서 하류로 흐르는 곡선이 서로를 비켜 간다. 컬럼 하나를 고르면
 * 그 컬럼으로 흘러드는 길과 흘러나가는 길만 불이 켜지고, 빛 알갱이가 그 위를 흐른다.
 */
import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { LINEAGE, TABLES, downstreamOf, upstreamOf, type Table } from "@/lib/concepts/anchor";
import { C, labelStyle, prefersReducedMotion } from "./theme";

const LAYER_X: Record<Table["layer"], number> = { source: -10.4, staging: -3.6, mart: 3.6, consumer: 10.2 };
const LAYER_KO: Record<Table["layer"], string> = { source: "원본", staging: "정리", mart: "분석", consumer: "소비" };
const CARD_W = 5.0;
const CARD_D = 0.5;
const ROW_H = 0.54;
const HEAD_H = 1.1;
const PAD = 0.4;
const GAP = 1.5;

interface Card {
  table: Table;
  x: number;
  y: number;
  h: number;
}

function layout(): Map<string, Card> {
  const out = new Map<string, Card>();
  const layers: Table["layer"][] = ["source", "staging", "mart", "consumer"];
  for (const layer of layers) {
    const ts = TABLES.filter((t) => t.layer === layer);
    const hs = ts.map((t) => HEAD_H + t.columns.length * ROW_H + PAD);
    const total = hs.reduce((a, b) => a + b, 0) + (ts.length - 1) * GAP;
    let top = total / 2;
    ts.forEach((t, i) => {
      out.set(t.name, { table: t, x: LAYER_X[layer], y: top - hs[i] / 2, h: hs[i] });
      top -= hs[i] + GAP;
    });
  }
  return out;
}

function colPoint(cards: Map<string, Card>, ref: string, side: "left" | "right" | "center"): THREE.Vector3 {
  const [tableName, colName] = ref.split(".");
  const card = cards.get(tableName)!;
  const i = card.table.columns.findIndex((c) => c.name === colName);
  const y = card.y + card.h / 2 - HEAD_H - i * ROW_H - ROW_H / 2;
  const x = side === "right" ? card.x + CARD_W / 2 : side === "left" ? card.x - CARD_W / 2 : card.x;
  return new THREE.Vector3(x, y, CARD_D / 2 + 0.08);
}

/** 상류 → 하류 곡선. 보는 사람 쪽(+Z)으로 부풀려 서로 비켜 가게 한다. */
function makeCurve(a: THREE.Vector3, b: THREE.Vector3, bow: number): THREE.CatmullRomCurve3 {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  return new THREE.CatmullRomCurve3([
    a,
    new THREE.Vector3(a.x + 1.5, a.y, a.z + bow * 0.6),
    new THREE.Vector3(mid.x, mid.y, mid.z + bow),
    new THREE.Vector3(b.x - 1.5, b.y, b.z + bow * 0.6),
    b,
  ]);
}

/**
 * 같은 층 안의 간선(fct_orders → daily_revenue)은 x 가 같아 왼쪽으로 되돌아가는 추한 고리가 된다.
 * 두 카드의 **오른쪽 끝**을 잡고 바깥으로 한 번 부푼 C 자로 내려보낸다.
 */
function makeSideCurve(a: THREE.Vector3, b: THREE.Vector3, bow: number): THREE.CatmullRomCurve3 {
  const out = Math.max(a.x, b.x) + 2.2;
  return new THREE.CatmullRomCurve3([
    a,
    new THREE.Vector3(out, a.y, a.z + bow * 0.5),
    new THREE.Vector3(out + 0.6, (a.y + b.y) / 2, a.z + bow),
    new THREE.Vector3(out, b.y, b.z + bow * 0.5),
    b,
  ]);
}

function FlowDot({ curve, color, offset }: { curve: THREE.CatmullRomCurve3; color: string; offset: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    const m = ref.current;
    if (!m) return;
    const t = (state.clock.elapsedTime * 0.18 + offset) % 1;
    m.position.copy(curve.getPointAt(t));
    m.scale.setScalar(0.8 + Math.sin(t * Math.PI) * 0.6);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.1, 10, 10]} />
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
  );
}

function Edge({ curve, state, color }: { curve: THREE.CatmullRomCurve3; state: "off" | "on"; color: string }) {
  const on = state === "on";
  return (
    <mesh>
      <tubeGeometry args={[curve, 48, on ? 0.055 : 0.02, 7, false]} />
      <meshStandardMaterial
        color={on ? color : C.line}
        emissive={on ? color : "#000000"}
        emissiveIntensity={on ? 1.5 : 0}
        roughness={0.5}
        transparent
        opacity={on ? 1 : 0.55}
        toneMapped={false}
      />
    </mesh>
  );
}

function ColumnBar({
  card,
  index,
  lit,
  selected,
  color,
  onSelect,
}: {
  card: Card;
  index: number;
  lit: boolean;
  selected: boolean;
  color: string;
  onSelect: () => void;
}) {
  const [hover, setHover] = useState(false);
  const col = card.table.columns[index];
  const y = card.y + card.h / 2 - HEAD_H - index * ROW_H - ROW_H / 2;
  const active = selected || lit;
  return (
    <group position={[card.x, y, CARD_D / 2 + 0.03]}>
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
        <boxGeometry args={[CARD_W - 0.5, ROW_H - 0.1, 0.12]} />
        <meshStandardMaterial
          color={selected ? color : active ? C.accentDim : hover ? "#221e1a" : C.raised}
          emissive={selected ? color : active ? color : "#000000"}
          emissiveIntensity={selected ? 0.9 : active ? 0.28 : 0}
          roughness={0.6}
          metalness={0.1}
        />
      </mesh>
      <Html position={[-(CARD_W - 0.5) / 2 + 0.16, 0, 0.1]} center={false} distanceFactor={14} zIndexRange={[20, 0]} style={labelStyle}>
        <span
          style={{
            fontSize: 12,
            color: selected ? C.bg : active ? C.ink : C.dim,
            fontWeight: selected ? 600 : 400,
            transform: "translateY(-50%)",
            display: "inline-block",
          }}
        >
          {col.name}
          {col.pii && <span style={{ marginLeft: 6, color: selected ? C.bg : C.bad, fontSize: 10 }}>PII</span>}
        </span>
      </Html>
    </group>
  );
}

function TableCard({ card, children }: { card: Card; children: React.ReactNode }) {
  const t = card.table;
  const box = useMemo(() => new THREE.BoxGeometry(CARD_W, card.h, CARD_D), [card.h]);
  return (
    <group>
      <mesh position={[card.x, card.y, 0]}>
        <boxGeometry args={[CARD_W, card.h, CARD_D]} />
        <meshStandardMaterial color={C.raised} roughness={0.85} metalness={0.05} />
      </mesh>
      {/* 테두리 — 얇은 프레임으로 카드가 공간에 떠 있게 보인다 */}
      <lineSegments position={[card.x, card.y, 0]}>
        <edgesGeometry args={[box]} />
        <lineBasicMaterial color={C.line} />
      </lineSegments>
      <Html position={[card.x - CARD_W / 2 + 0.2, card.y + card.h / 2 - HEAD_H / 2, CARD_D / 2 + 0.05]} distanceFactor={14} zIndexRange={[25, 0]} style={labelStyle}>
        <span style={{ display: "inline-block", transform: "translateY(-50%)", lineHeight: 1.25 }}>
          <span style={{ fontSize: 15, color: C.ink }}>{t.name}</span>
          <br />
          <span style={{ fontSize: 10.5, color: t.owner ? C.faint : C.bad }}>
            {t.owner ?? "오너 없음"} · {t.freshness}
          </span>
        </span>
      </Html>
      {children}
    </group>
  );
}

function Scene({ mode, selected, setSelected }: { mode: "lineage" | "incident"; selected: string; setSelected: (s: string) => void }) {
  const cards = useMemo(() => layout(), []);
  const up = useMemo(() => upstreamOf(selected), [selected]);
  const down = useMemo(() => downstreamOf(selected), [selected]);
  const lit = useMemo(() => new Set([selected, ...up, ...down]), [selected, up, down]);
  const color = mode === "incident" ? C.bad : C.accent;
  const reduced = useMemo(() => prefersReducedMotion(), []);

  const edges = useMemo(
    () =>
      LINEAGE.map((e, i) => {
        const sameLayer = cards.get(e.from.split(".")[0])!.x === cards.get(e.to.split(".")[0])!.x;
        const a = colPoint(cards, e.from, "right");
        const b = colPoint(cards, e.to, sameLayer ? "right" : "left");
        const bow = 1.2 + (i % 4) * 0.55;
        const on = lit.has(e.from) && lit.has(e.to);
        return { key: `${e.from}->${e.to}`, curve: sameLayer ? makeSideCurve(a, b, bow) : makeCurve(a, b, bow), on, offset: (i % 5) / 5 };
      }),
    [cards, lit],
  );
  const flowing = edges.filter((e) => e.on).slice(0, 14);

  return (
    <>
      <color attach="background" args={[C.bg]} />
      <fog attach="fog" args={[C.bg, 26, 58]} />
      <ambientLight intensity={0.95} />
      <directionalLight position={[6, 10, 14]} intensity={0.7} color={C.ink} />
      <pointLight position={[0, 0, 12]} intensity={90} distance={40} color={color} />

      {[...cards.values()].map((card) => (
        <TableCard key={card.table.name} card={card}>
          {card.table.columns.map((col, i) => {
            const ref = `${card.table.name}.${col.name}`;
            return (
              <ColumnBar
                key={col.name}
                card={card}
                index={i}
                lit={lit.has(ref)}
                selected={ref === selected}
                color={color}
                onSelect={() => setSelected(ref)}
              />
            );
          })}
        </TableCard>
      ))}

      {edges.map((e) => (
        <Edge key={e.key} curve={e.curve} state={e.on ? "on" : "off"} color={color} />
      ))}
      {!reduced && flowing.map((e) => <FlowDot key={`d-${e.key}`} curve={e.curve} color={color} offset={e.offset} />)}

      {(["source", "staging", "mart", "consumer"] as const).map((l) => (
        <Html key={l} position={[LAYER_X[l], 7.4, 0]} center distanceFactor={16} zIndexRange={[10, 0]} style={labelStyle}>
          <span style={{ fontSize: 13, color: C.faint, letterSpacing: "0.2em" }}>{LAYER_KO[l]}</span>
        </Html>
      ))}

      <OrbitControls
        enablePan={false}
        enableDamping
        dampingFactor={0.08}
        minDistance={14}
        maxDistance={38}
        minPolarAngle={Math.PI * 0.3}
        maxPolarAngle={Math.PI * 0.64}
        minAzimuthAngle={-0.34}
        maxAzimuthAngle={0.34}
        autoRotate={!reduced}
        autoRotateSpeed={0.18}
      />
    </>
  );
}

export function Pipeline3D({ mode = "lineage", initial }: { mode?: "lineage" | "incident"; initial?: string }) {
  const [selected, setSelected] = useState(initial ?? (mode === "incident" ? "orders_raw.currency" : "daily_revenue.revenue_krw"));
  const up = useMemo(() => upstreamOf(selected), [selected]);
  const down = useMemo(() => downstreamOf(selected), [selected]);
  const options = useMemo(() => TABLES.flatMap((t) => t.columns.map((c) => `${t.name}.${c.name}`)), []);

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        <label htmlFor="p3d-col" className="text-dim">
          {mode === "incident" ? "이상이 난 컬럼" : "기준 컬럼"}
        </label>
        <select id="p3d-col" value={selected} onChange={(e) => setSelected(e.target.value)} className="rounded border border-line bg-bg px-2 py-1 font-mono text-xs">
          {options.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <span className="text-xs text-faint">상류 {up.size} · 하류 {down.size}</span>
      </div>
      <div className="overflow-hidden rounded-lg border border-line" style={{ height: 520 }} aria-label="3D 컬럼 리니지 장면">
        <Canvas dpr={[1, 1.8]} camera={{ position: [0, 2.2, 24], fov: 40 }} gl={{ antialias: true }}>
          <Scene mode={mode} selected={selected} setSelected={setSelected} />
        </Canvas>
      </div>
      <p className="mt-2 text-xs text-dim">
        끌면 각도가 바뀌고, 휠로 멀고 가까워진다. 컬럼 막대를 누르면 기준이 바뀐다.{" "}
        {mode === "incident"
          ? `${selected} 에 이상이 나면 붉은 길을 따라 하류 ${down.size}개 컬럼이 물든다. 관측이 경보를 내고, 리니지가 누구에게 알릴지 정한다.`
          : `${selected} 로 흘러드는 상류 ${up.size}개 컬럼에 불이 켜진다. 그중 하나가 틀리면 이 값도 틀린다.`}
      </p>
    </div>
  );
}
