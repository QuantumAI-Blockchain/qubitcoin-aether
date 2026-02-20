"use client";

import { useRef, useMemo, useCallback, useState } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import { api, type KnowledgeGraphData } from "@/lib/api";
import { Card } from "@/components/ui/card";
import * as THREE from "three";

/* --- Types --- */

type KnowledgeNode = KnowledgeGraphData["nodes"][number];
type KnowledgeEdge = KnowledgeGraphData["edges"][number];

/* --- Force layout (simple spring simulation) --- */

interface NodePosition {
  id: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
}

function layoutNodes(
  nodes: KnowledgeNode[],
  edges: KnowledgeEdge[],
): NodePosition[] {
  // Place nodes on a sphere initially, then run a few iterations of force layout
  const positions: NodePosition[] = nodes.map((n, i) => {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / nodes.length);
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const r = 3 + Math.random() * 0.5;
    return {
      id: n.id,
      x: r * Math.sin(phi) * Math.cos(theta),
      y: r * Math.sin(phi) * Math.sin(theta),
      z: r * Math.cos(phi),
      vx: 0,
      vy: 0,
      vz: 0,
    };
  });

  const idxMap = new Map<number, number>();
  positions.forEach((p, i) => idxMap.set(p.id, i));

  // Run 80 iterations of simple force simulation
  for (let iter = 0; iter < 80; iter++) {
    const cooling = 1 - iter / 80;

    // Repulsion (Coulomb)
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const dx = positions[i].x - positions[j].x;
        const dy = positions[i].y - positions[j].y;
        const dz = positions[i].z - positions[j].z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
        const force = (0.8 * cooling) / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        const fz = (dz / dist) * force;
        positions[i].vx += fx;
        positions[i].vy += fy;
        positions[i].vz += fz;
        positions[j].vx -= fx;
        positions[j].vy -= fy;
        positions[j].vz -= fz;
      }
    }

    // Attraction (spring) along edges
    for (const edge of edges) {
      const si = idxMap.get(edge.source);
      const ti = idxMap.get(edge.target);
      if (si === undefined || ti === undefined) continue;
      const dx = positions[ti].x - positions[si].x;
      const dy = positions[ti].y - positions[si].y;
      const dz = positions[ti].z - positions[si].z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
      const force = 0.05 * cooling * (dist - 1.5);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      const fz = (dz / dist) * force;
      positions[si].vx += fx;
      positions[si].vy += fy;
      positions[si].vz += fz;
      positions[ti].vx -= fx;
      positions[ti].vy -= fy;
      positions[ti].vz -= fz;
    }

    // Apply velocities with damping
    for (const p of positions) {
      p.x += p.vx * 0.3;
      p.y += p.vy * 0.3;
      p.z += p.vz * 0.3;
      p.vx *= 0.6;
      p.vy *= 0.6;
      p.vz *= 0.6;
    }
  }

  return positions;
}

/* --- Node colour by type --- */

const NODE_COLORS: Record<string, string> = {
  assertion: "#00ff88",   // quantum-green
  observation: "#7c3aed", // quantum-violet
  inference: "#f59e0b",   // golden
  axiom: "#3b82f6",       // blue
};

const EDGE_COLORS: Record<string, string> = {
  supports: "#00ff8840",
  contradicts: "#ef444440",
  derives: "#7c3aed40",
  requires: "#f59e0b40",
  refines: "#3b82f640",
};

/* --- 3D scene components --- */

function GraphNode({
  position,
  node,
  onHover,
  onUnhover,
}: {
  position: [number, number, number];
  node: KnowledgeNode;
  onHover: (node: KnowledgeNode, e: ThreeEvent<PointerEvent>) => void;
  onUnhover: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const color = NODE_COLORS[node.node_type] ?? "#94a3b8";
  const size = 0.06 + node.confidence * 0.08;

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.scale.setScalar(
        1 + Math.sin(clock.elapsedTime * 2 + node.id) * 0.08,
      );
    }
  });

  return (
    <mesh
      ref={meshRef}
      position={position}
      onPointerOver={(e) => onHover(node, e)}
      onPointerOut={onUnhover}
    >
      <sphereGeometry args={[size, 12, 12]} />
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={0.5}
        transparent
        opacity={0.85}
      />
    </mesh>
  );
}

function GraphEdges({
  edges,
  posMap,
}: {
  edges: KnowledgeEdge[];
  posMap: Map<number, [number, number, number]>;
}) {
  const lineSegments = useMemo(() => {
    const positions: number[] = [];
    const colors: number[] = [];

    for (const edge of edges) {
      const src = posMap.get(edge.source);
      const tgt = posMap.get(edge.target);
      if (!src || !tgt) continue;
      positions.push(...src, ...tgt);

      const hexColor = EDGE_COLORS[edge.edge_type] ?? "#ffffff30";
      const c = new THREE.Color(hexColor.slice(0, 7));
      colors.push(c.r, c.g, c.b, c.r, c.g, c.b);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return geo;
  }, [edges, posMap]);

  return (
    <lineSegments geometry={lineSegments}>
      <lineBasicMaterial vertexColors transparent opacity={0.35} />
    </lineSegments>
  );
}

function RotatingGroup({ children }: { children: React.ReactNode }) {
  const groupRef = useRef<THREE.Group>(null!);
  useFrame((_state, delta) => {
    if (groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05;
    }
  });
  return <group ref={groupRef}>{children}</group>;
}

/* --- Main scene --- */

function GraphScene({ data }: { data: KnowledgeGraphData }) {
  const [hoveredNode, setHoveredNode] = useState<KnowledgeNode | null>(null);
  const [labelPos, setLabelPos] = useState<[number, number, number]>([0, 0, 0]);

  const { positions, posMap } = useMemo(() => {
    const laidOut = layoutNodes(data.nodes, data.edges);
    const pm = new Map<number, [number, number, number]>();
    for (const p of laidOut) {
      pm.set(p.id, [p.x, p.y, p.z]);
    }
    return { positions: laidOut, posMap: pm };
  }, [data]);

  const handleHover = useCallback(
    (node: KnowledgeNode, e: ThreeEvent<PointerEvent>) => {
      setHoveredNode(node);
      if (e.point) setLabelPos([e.point.x, e.point.y + 0.3, e.point.z]);
    },
    [],
  );

  const handleUnhover = useCallback(() => {
    setHoveredNode(null);
  }, []);

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={0.6} />
      <OrbitControls
        enablePan
        enableZoom
        enableRotate
        autoRotate={false}
        dampingFactor={0.1}
      />
      <RotatingGroup>
        <GraphEdges edges={data.edges} posMap={posMap} />
        {positions.map((p) => {
          const node = data.nodes.find((n) => n.id === p.id);
          if (!node) return null;
          return (
            <GraphNode
              key={p.id}
              position={[p.x, p.y, p.z]}
              node={node}
              onHover={handleHover}
              onUnhover={handleUnhover}
            />
          );
        })}
      </RotatingGroup>
      {hoveredNode && (
        <Text
          position={labelPos}
          fontSize={0.15}
          color="#e2e8f0"
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.01}
          outlineColor="#0a0a0f"
        >
          {hoveredNode.content.slice(0, 50)}
          {hoveredNode.content.length > 50 ? "..." : ""}
        </Text>
      )}
    </>
  );
}

/* --- Exported component --- */

export function KnowledgeGraph3D() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["knowledgeGraph"],
    queryFn: () => api.getKnowledgeGraph(),
    refetchInterval: 30_000,
    retry: false,
  });

  // Legend items
  const legend = [
    { label: "Assertion", color: NODE_COLORS.assertion },
    { label: "Observation", color: NODE_COLORS.observation },
    { label: "Inference", color: NODE_COLORS.inference },
    { label: "Axiom", color: NODE_COLORS.axiom },
  ];

  return (
    <Card>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-[family-name:var(--font-heading)] text-lg font-semibold">
          Knowledge Graph
        </h3>
        <div className="flex gap-3">
          {legend.map((l) => (
            <span key={l.label} className="flex items-center gap-1 text-xs text-text-secondary">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ backgroundColor: l.color }}
              />
              {l.label}
            </span>
          ))}
        </div>
      </div>

      <div className="relative h-[400px] w-full overflow-hidden rounded-lg bg-void">
        {isLoading && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-secondary">
            Loading knowledge graph...
          </div>
        )}
        {isError && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-secondary">
            <div className="text-center">
              <p>Unable to load knowledge graph.</p>
              <p className="mt-1 text-xs">The node may be offline.</p>
            </div>
          </div>
        )}
        {data && data.nodes.length > 0 && (
          <Canvas camera={{ position: [0, 0, 8], fov: 50 }}>
            <GraphScene data={data} />
          </Canvas>
        )}
        {data && data.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-secondary">
            No knowledge nodes yet. Start mining to build the graph.
          </div>
        )}
      </div>

      {data && (
        <div className="mt-3 flex gap-6 text-xs text-text-secondary">
          <span>
            Nodes: <span className="font-[family-name:var(--font-mono)] text-text-primary">{data.nodes.length}</span>
          </span>
          <span>
            Edges: <span className="font-[family-name:var(--font-mono)] text-text-primary">{data.edges.length}</span>
          </span>
        </div>
      )}
    </Card>
  );
}
