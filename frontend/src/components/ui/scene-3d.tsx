"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { useRef, useMemo } from "react";
import * as THREE from "three";

/* ── Floating Particles ── */
function Particles({ count = 80 }: { count?: number }) {
  const mesh = useRef<THREE.Points>(null);

  const particles = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 10;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 5;
      // Blue-cyan gradient colors
      const t = Math.random();
      colors[i * 3] = 0.23 + t * 0.1;     // R
      colors[i * 3 + 1] = 0.55 + t * 0.3; // G
      colors[i * 3 + 2] = 1.0;             // B
    }
    return { positions, colors };
  }, [count]);

  useFrame((state) => {
    if (!mesh.current) return;
    mesh.current.rotation.y = state.clock.elapsedTime * 0.03;
    mesh.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.02) * 0.1;
  });

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[particles.positions, 3]}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[particles.colors, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        vertexColors
        transparent
        opacity={0.8}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/* ── Connection Lines (network effect) ── */
function ConnectionLines() {
  const ref = useRef<THREE.LineSegments>(null);

  const geometry = useMemo(() => {
    const points: number[] = [];
    const nodes: [number, number, number][] = [];

    // Create node positions
    for (let i = 0; i < 20; i++) {
      nodes.push([
        (Math.random() - 0.5) * 6,
        (Math.random() - 0.5) * 4,
        (Math.random() - 0.5) * 3,
      ]);
    }

    // Connect nearby nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dist = Math.sqrt(
          (nodes[i][0] - nodes[j][0]) ** 2 +
          (nodes[i][1] - nodes[j][1]) ** 2 +
          (nodes[i][2] - nodes[j][2]) ** 2,
        );
        if (dist < 3) {
          points.push(...nodes[i], ...nodes[j]);
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
    return geo;
  }, []);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.elapsedTime * 0.02;
  });

  return (
    <lineSegments ref={ref} geometry={geometry}>
      <lineBasicMaterial color="#3b8bff" transparent opacity={0.15} />
    </lineSegments>
  );
}

/* ── Glowing Ring ── */
function GlowRing() {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.x = Math.PI / 2 + Math.sin(state.clock.elapsedTime * 0.5) * 0.1;
    ref.current.rotation.z = state.clock.elapsedTime * 0.1;
  });

  return (
    <mesh ref={ref} position={[0, 0, -2]}>
      <torusGeometry args={[2.5, 0.01, 16, 100]} />
      <meshBasicMaterial color="#3b8bff" transparent opacity={0.3} />
    </mesh>
  );
}

/* ── Main Scene Export ── */
export function Scene3D({ className }: { className?: string }) {
  return (
    <div className={`pointer-events-none absolute inset-0 ${className ?? ""}`}>
      <Canvas
        camera={{ position: [0, 0, 5], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <ambientLight intensity={0.5} />
        <Particles count={100} />
        <ConnectionLines />
        <GlowRing />
      </Canvas>
    </div>
  );
}

/* ── Login Scene (simpler, focused) ── */
export function LoginScene() {
  return (
    <div className="pointer-events-none absolute inset-0 opacity-70">
      <Canvas
        camera={{ position: [0, 0, 4], fov: 50 }}
        gl={{ antialias: true, alpha: true }}
        style={{ background: "transparent" }}
      >
        <Particles count={60} />
        <GlowRing />
      </Canvas>
    </div>
  );
}
