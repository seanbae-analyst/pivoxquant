"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { useRef, useMemo } from "react";
import * as THREE from "three";
import { Card } from "@/components/ui/card";
import type { HistoryPoint } from "@/lib/types";

function ChartMesh({ data }: { data: HistoryPoint[] }) {
  const meshRef = useRef<THREE.Mesh>(null);

  const geometry = useMemo(() => {
    if (data.length < 2) return new THREE.BufferGeometry();

    const values = data.map((d) => d.value);
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;
    const n = data.length;

    // Create 3D surface: width = time, depth = constant, height = value
    const width = 4;
    const depth = 1.5;
    const vertices: number[] = [];
    const colors: number[] = [];
    const indices: number[] = [];

    const rows = 8; // depth segments

    for (let z = 0; z <= rows; z++) {
      for (let i = 0; i < n; i++) {
        const x = (i / (n - 1)) * width - width / 2;
        const normalized = (values[i] - minVal) / range;
        // Add depth wave effect
        const zFactor = Math.sin((z / rows) * Math.PI) * 0.3;
        const y = normalized * 1.5 + zFactor * normalized;
        const zPos = (z / rows) * depth - depth / 2;

        vertices.push(x, y, zPos);

        // Color: green gradient for gains, darker at base
        const isUp = values[values.length - 1] >= values[0];
        if (isUp) {
          colors.push(0.0 + normalized * 0.2, 0.5 + normalized * 0.4, 0.3 + normalized * 0.3);
        } else {
          colors.push(0.8 + normalized * 0.2, 0.1 + normalized * 0.2, 0.2);
        }

        // Create triangles
        if (i < n - 1 && z < rows) {
          const curr = z * n + i;
          const next = curr + 1;
          const below = curr + n;
          const belowNext = below + 1;
          indices.push(curr, below, next);
          indices.push(next, below, belowNext);
        }
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    geo.setIndex(indices);
    geo.computeVertexNormals();
    return geo;
  }, [data]);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.2) * 0.05 - 0.3;
    }
  });

  return (
    <mesh ref={meshRef} geometry={geometry} rotation={[-0.5, -0.3, 0]} position={[0, -0.3, 0]}>
      <meshStandardMaterial
        vertexColors
        transparent
        opacity={0.85}
        side={THREE.DoubleSide}
        metalness={0.3}
        roughness={0.6}
      />
    </mesh>
  );
}

/* Grid floor */
function Grid() {
  return (
    <gridHelper
      args={[6, 12, "#1a2540", "#0d1525"]}
      position={[0, -0.35, 0]}
      rotation={[0, 0, 0]}
    />
  );
}

interface Props {
  data: HistoryPoint[];
}

export function PnlChart3D({ data }: Props) {
  if (!data || data.length < 2) return null;

  const lastVal = data[data.length - 1]?.value ?? 0;
  const firstVal = data[0]?.value ?? 0;
  const pnl = ((lastVal - firstVal) / firstVal) * 100;
  const isUp = pnl >= 0;

  return (
    <Card className="border-border bg-card/80 p-5 backdrop-blur">
      <div className="mb-2 flex items-center justify-between">
        <p className="font-mono text-[9px] font-semibold uppercase tracking-[1.5px] text-muted-foreground/50">
          Portfolio Value — 3D
        </p>
        <span className={`font-mono text-sm font-bold ${isUp ? "text-success" : "text-destructive"}`}>
          {isUp ? "+" : ""}{pnl.toFixed(1)}%
        </span>
      </div>
      <div className="h-[250px] overflow-hidden rounded-lg">
        <Canvas camera={{ position: [0, 1.5, 3.5], fov: 45 }}>
          <ambientLight intensity={0.4} />
          <directionalLight position={[3, 5, 2]} intensity={0.8} color="#ffffff" />
          <pointLight position={[-3, 2, 2]} intensity={0.3} color="#3b8bff" />
          <ChartMesh data={data} />
          <Grid />
          <OrbitControls
            enableZoom={false}
            enablePan={false}
            minPolarAngle={0.5}
            maxPolarAngle={1.3}
            autoRotate
            autoRotateSpeed={0.5}
          />
        </Canvas>
      </div>
    </Card>
  );
}
