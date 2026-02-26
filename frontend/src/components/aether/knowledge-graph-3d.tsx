"use client";

import { useRef, useMemo, useCallback, useState } from "react";
import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Text } from "@react-three/drei";
import { useQuery } from "@tanstack/react-query";
import { api, type KnowledgeGraphData, type KnowledgeGraphNode, type KnowledgeGraphEdge } from "@/lib/api";
import { Card } from "@/components/ui/card";
import * as THREE from "three";

/* --- Force layout (simple spring simulation) --- */

interface NodePosition {
  id: number;
  x: number;
  y: number;
  z: number;
  vx: number;
  vy: number;
  vz: number;
  fixed?: boolean;
}

/* --- Tree of Life fixed positions for Sephirot --- */

const SEPHIROT_POSITIONS: Record<string, [number, number, number]> = {
  Keter:    [0,    4.0,  0],
  Chochmah: [1.5,  3.0,  0.4],
  Binah:    [-1.5, 3.0, -0.4],
  Chesed:   [1.5,  1.5,  0.3],
  Gevurah:  [-1.5, 1.5, -0.3],
  Tiferet:  [0,    1.0,  0],
  Netzach:  [1.5, -0.5,  0.3],
  Hod:      [-1.5,-0.5, -0.3],
  Yesod:    [0,   -1.5,  0],
  Malkuth:  [0,   -3.0,  0],
};

function layoutNodes(
  nodes: KnowledgeGraphNode[],
  edges: KnowledgeGraphEdge[],
): NodePosition[] {
  const sephirotNodes: NodePosition[] = [];
  const regularNodes: KnowledgeGraphNode[] = [];

  for (const n of nodes) {
    if (n.node_type === "sephirot" && n.sephirot_name) {
      const pos = SEPHIROT_POSITIONS[n.sephirot_name];
      if (pos) {
        sephirotNodes.push({
          id: n.id,
          x: pos[0],
          y: pos[1],
          z: pos[2],
          vx: 0, vy: 0, vz: 0,
          fixed: true,
        });
        continue;
      }
    }
    regularNodes.push(n);
  }

  // Place regular nodes on a sphere initially
  const positions: NodePosition[] = regularNodes.map((n, i) => {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / Math.max(regularNodes.length, 1));
    const theta = Math.PI * (1 + Math.sqrt(5)) * i;
    const r = 5 + Math.random() * 0.5;
    return {
      id: n.id,
      x: r * Math.sin(phi) * Math.cos(theta),
      y: r * Math.sin(phi) * Math.sin(theta),
      z: r * Math.cos(phi),
      vx: 0, vy: 0, vz: 0,
    };
  });

  const allPositions = [...sephirotNodes, ...positions];
  const idxMap = new Map<number, number>();
  allPositions.forEach((p, i) => idxMap.set(p.id, i));

  // Run 80 iterations of simple force simulation (skip fixed sephirot)
  for (let iter = 0; iter < 80; iter++) {
    const cooling = 1 - iter / 80;

    // Repulsion (Coulomb)
    for (let i = 0; i < allPositions.length; i++) {
      for (let j = i + 1; j < allPositions.length; j++) {
        const dx = allPositions[i].x - allPositions[j].x;
        const dy = allPositions[i].y - allPositions[j].y;
        const dz = allPositions[i].z - allPositions[j].z;
        const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
        const force = (0.8 * cooling) / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        const fz = (dz / dist) * force;
        if (!allPositions[i].fixed) {
          allPositions[i].vx += fx;
          allPositions[i].vy += fy;
          allPositions[i].vz += fz;
        }
        if (!allPositions[j].fixed) {
          allPositions[j].vx -= fx;
          allPositions[j].vy -= fy;
          allPositions[j].vz -= fz;
        }
      }
    }

    // Attraction (spring) along edges
    for (const edge of edges) {
      const si = idxMap.get(edge.source);
      const ti = idxMap.get(edge.target);
      if (si === undefined || ti === undefined) continue;
      const dx = allPositions[ti].x - allPositions[si].x;
      const dy = allPositions[ti].y - allPositions[si].y;
      const dz = allPositions[ti].z - allPositions[si].z;
      const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) + 0.01;
      const force = 0.05 * cooling * (dist - 1.5);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      const fz = (dz / dist) * force;
      if (!allPositions[si].fixed) {
        allPositions[si].vx += fx;
        allPositions[si].vy += fy;
        allPositions[si].vz += fz;
      }
      if (!allPositions[ti].fixed) {
        allPositions[ti].vx -= fx;
        allPositions[ti].vy -= fy;
        allPositions[ti].vz -= fz;
      }
    }

    // Apply velocities with damping (only non-fixed)
    for (const p of allPositions) {
      if (p.fixed) continue;
      p.x += p.vx * 0.3;
      p.y += p.vy * 0.3;
      p.z += p.vz * 0.3;
      p.vx *= 0.6;
      p.vy *= 0.6;
      p.vz *= 0.6;
    }
  }

  return allPositions;
}

/* --- Colour palettes --- */

const NODE_COLORS: Record<string, string> = {
  assertion: "#00ff88",
  observation: "#7c3aed",
  inference: "#f59e0b",
  axiom: "#3b82f6",
  sephirot: "#ec4899",
  contract: "#06b6d4",
};

const SEPHIROT_COLORS: Record<string, string> = {
  Keter: "#c084fc",
  Chochmah: "#60a5fa",
  Binah: "#f472b6",
  Chesed: "#34d399",
  Gevurah: "#f87171",
  Tiferet: "#fbbf24",
  Netzach: "#a78bfa",
  Hod: "#fb923c",
  Yesod: "#2dd4bf",
  Malkuth: "#4ade80",
};

const EDGE_COLORS: Record<string, string> = {
  supports: "#00ff88",
  contradicts: "#ef4444",
  derives: "#7c3aed",
  requires: "#f59e0b",
  refines: "#3b82f6",
};

/* --- Filter types --- */

type NodeFilter = "all" | "assertion" | "observation" | "inference" | "axiom" | "sephirot" | "contract";
type EdgeFilter = "supports" | "contradicts" | "derives" | "requires" | "refines";

const NODE_FILTER_LABELS: { key: NodeFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "assertion", label: "Assertion" },
  { key: "observation", label: "Observation" },
  { key: "inference", label: "Inference" },
  { key: "axiom", label: "Axiom" },
  { key: "sephirot", label: "Sephirot" },
  { key: "contract", label: "Contracts" },
];

const EDGE_FILTER_LABELS: { key: EdgeFilter; label: string }[] = [
  { key: "supports", label: "Supports" },
  { key: "contradicts", label: "Contradicts" },
  { key: "derives", label: "Derives" },
  { key: "requires", label: "Requires" },
  { key: "refines", label: "Refines" },
];

/* --- 3D scene components --- */

function GraphNode({
  position,
  node,
  dimmed,
  onHover,
  onUnhover,
}: {
  position: [number, number, number];
  node: KnowledgeGraphNode;
  dimmed: boolean;
  onHover: (node: KnowledgeGraphNode, e: ThreeEvent<PointerEvent>) => void;
  onUnhover: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null!);
  const isSephirot = node.node_type === "sephirot";
  const isContract = node.is_contract === true;

  const color = isSephirot
    ? (SEPHIROT_COLORS[node.sephirot_name ?? ""] ?? NODE_COLORS.sephirot)
    : isContract
      ? NODE_COLORS.contract
      : (NODE_COLORS[node.node_type] ?? "#94a3b8");

  const size = isSephirot ? 0.25 : 0.04 + node.confidence * 0.1;
  const opacity = dimmed ? 0.12 : 0.85;
  const emissiveIntensity = dimmed ? 0.1 : isSephirot ? 0.8 : 0.5;

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const pulse = isSephirot
        ? 1 + Math.sin(clock.elapsedTime * 1.5 + node.id) * 0.12
        : 1 + Math.sin(clock.elapsedTime * 2 + node.id) * 0.08;
      meshRef.current.scale.setScalar(pulse);
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => onHover(node, e)}
        onPointerOut={onUnhover}
      >
        {isContract && !isSephirot ? (
          <icosahedronGeometry args={[size, 1]} />
        ) : (
          <sphereGeometry args={[size, isSephirot ? 24 : 12, isSephirot ? 24 : 12]} />
        )}
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={emissiveIntensity}
          transparent
          opacity={opacity}
        />
      </mesh>
      {isSephirot && !dimmed && (
        <Text
          position={[0, size + 0.15, 0]}
          fontSize={0.14}
          color={color}
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.008}
          outlineColor="#0a0a0f"
        >
          {node.sephirot_name}
        </Text>
      )}
    </group>
  );
}

function GraphEdges({
  edges,
  posMap,
  hiddenEdgeTypes,
  dimmedNodeIds,
}: {
  edges: KnowledgeGraphEdge[];
  posMap: Map<number, [number, number, number]>;
  hiddenEdgeTypes: Set<string>;
  dimmedNodeIds: Set<number>;
}) {
  const lineSegments = useMemo(() => {
    const positions: number[] = [];
    const colors: number[] = [];

    for (const edge of edges) {
      if (hiddenEdgeTypes.has(edge.edge_type)) continue;
      const src = posMap.get(edge.source);
      const tgt = posMap.get(edge.target);
      if (!src || !tgt) continue;

      const bothDimmed = dimmedNodeIds.has(edge.source) && dimmedNodeIds.has(edge.target);
      positions.push(...src, ...tgt);

      const hexColor = EDGE_COLORS[edge.edge_type] ?? "#ffffff";
      const c = new THREE.Color(hexColor);
      const alpha = bothDimmed ? 0.3 : 1.0;
      colors.push(c.r * alpha, c.g * alpha, c.b * alpha, c.r * alpha, c.g * alpha, c.b * alpha);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    return geo;
  }, [edges, posMap, hiddenEdgeTypes, dimmedNodeIds]);

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
      groupRef.current.rotation.y += delta * 0.04;
    }
  });
  return <group ref={groupRef}>{children}</group>;
}

/* --- Main scene --- */

function GraphScene({
  data,
  activeNodeFilter,
  hiddenEdgeTypes,
}: {
  data: KnowledgeGraphData;
  activeNodeFilter: NodeFilter;
  hiddenEdgeTypes: Set<string>;
}) {
  const [hoveredNode, setHoveredNode] = useState<KnowledgeGraphNode | null>(null);
  const [labelPos, setLabelPos] = useState<[number, number, number]>([0, 0, 0]);

  const { positions, posMap } = useMemo(() => {
    const laidOut = layoutNodes(data.nodes, data.edges);
    const pm = new Map<number, [number, number, number]>();
    for (const p of laidOut) {
      pm.set(p.id, [p.x, p.y, p.z]);
    }
    return { positions: laidOut, posMap: pm };
  }, [data]);

  // Determine which nodes are dimmed by the filter
  const dimmedNodeIds = useMemo(() => {
    if (activeNodeFilter === "all") return new Set<number>();
    const dimmed = new Set<number>();
    for (const n of data.nodes) {
      let matches = false;
      if (activeNodeFilter === "contract") {
        matches = n.is_contract === true;
      } else {
        matches = n.node_type === activeNodeFilter;
      }
      if (!matches) dimmed.add(n.id);
    }
    return dimmed;
  }, [data.nodes, activeNodeFilter]);

  const handleHover = useCallback(
    (node: KnowledgeGraphNode, e: ThreeEvent<PointerEvent>) => {
      setHoveredNode(node);
      if (e.point) setLabelPos([e.point.x, e.point.y + 0.35, e.point.z]);
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
        <GraphEdges
          edges={data.edges}
          posMap={posMap}
          hiddenEdgeTypes={hiddenEdgeTypes}
          dimmedNodeIds={dimmedNodeIds}
        />
        {positions.map((p) => {
          const node = data.nodes.find((n) => n.id === p.id);
          if (!node) return null;
          return (
            <GraphNode
              key={p.id}
              position={[p.x, p.y, p.z]}
              node={node}
              dimmed={dimmedNodeIds.has(p.id)}
              onHover={handleHover}
              onUnhover={handleUnhover}
            />
          );
        })}
      </RotatingGroup>
      {hoveredNode && (
        <Text
          position={labelPos}
          fontSize={0.13}
          color="#e2e8f0"
          anchorX="center"
          anchorY="bottom"
          outlineWidth={0.01}
          outlineColor="#0a0a0f"
          maxWidth={4}
        >
          {`[${hoveredNode.node_type}] ${hoveredNode.content.slice(0, 60)}${hoveredNode.content.length > 60 ? "..." : ""}\nConf: ${(hoveredNode.confidence * 100).toFixed(0)}%${hoveredNode.source_block != null ? ` | Block #${hoveredNode.source_block}` : ""}`}
        </Text>
      )}
    </>
  );
}

/* --- Filter toggle button --- */

function FilterBtn({
  label,
  active,
  color,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  color?: string;
  count?: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium transition-colors ${
        active
          ? "bg-border-subtle text-text-primary ring-1 ring-quantum-green/40"
          : "bg-bg-panel text-text-secondary hover:text-text-primary hover:bg-border-subtle"
      }`}
    >
      {color && (
        <span
          className="inline-block h-2 w-2 rounded-full shrink-0"
          style={{ backgroundColor: color }}
        />
      )}
      {label}
      {count !== undefined && (
        <span className="ml-0.5 font-[family-name:var(--font-code)] text-[10px] opacity-60">
          {count}
        </span>
      )}
    </button>
  );
}

/* --- Exported component --- */

export function KnowledgeGraph3D() {
  const [activeNodeFilter, setActiveNodeFilter] = useState<NodeFilter>("all");
  const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useQuery({
    queryKey: ["knowledgeGraph"],
    queryFn: () => api.getKnowledgeGraph(),
    refetchInterval: 15_000,
    retry: false,
  });

  // Count nodes by category for filter badges
  const nodeCounts = useMemo(() => {
    if (!data) return {} as Record<string, number>;
    const counts: Record<string, number> = { all: data.nodes.length };
    for (const n of data.nodes) {
      counts[n.node_type] = (counts[n.node_type] ?? 0) + 1;
      if (n.is_contract) counts["contract"] = (counts["contract"] ?? 0) + 1;
    }
    return counts;
  }, [data]);

  const toggleEdgeType = useCallback((edgeType: string) => {
    setHiddenEdgeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(edgeType)) {
        next.delete(edgeType);
      } else {
        next.add(edgeType);
      }
      return next;
    });
  }, []);

  // Use real totals from API, falling back to visible count
  const totalNodes = data?.total_nodes ?? data?.nodes.length ?? 0;
  const totalEdges = data?.total_edges ?? data?.edges.length ?? 0;
  const visibleNodes = data?.nodes.filter((n) => n.node_type !== "sephirot").length ?? 0;

  return (
    <Card>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Knowledge Graph
        </h3>
        {data && (
          <div className="flex gap-4 text-xs text-text-secondary font-[family-name:var(--font-code)]">
            <span>
              Showing <span className="text-text-primary">{visibleNodes}</span> of{" "}
              <span className="text-quantum-green">{totalNodes}</span> nodes
            </span>
            <span>
              <span className="text-text-primary">{totalEdges}</span> edges
            </span>
          </div>
        )}
      </div>

      {/* Node type filters */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {NODE_FILTER_LABELS.map((f) => (
          <FilterBtn
            key={f.key}
            label={f.label}
            active={activeNodeFilter === f.key}
            color={f.key === "all" ? undefined : (f.key === "contract" ? NODE_COLORS.contract : NODE_COLORS[f.key])}
            count={nodeCounts[f.key]}
            onClick={() => setActiveNodeFilter(f.key)}
          />
        ))}
      </div>

      {/* Edge type filters */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {EDGE_FILTER_LABELS.map((f) => (
          <FilterBtn
            key={f.key}
            label={f.label}
            active={!hiddenEdgeTypes.has(f.key)}
            color={EDGE_COLORS[f.key]}
            onClick={() => toggleEdgeType(f.key)}
          />
        ))}
      </div>

      <div className="relative h-[500px] w-full overflow-hidden rounded-lg bg-bg-deep">
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
          <Canvas camera={{ position: [0, 0, 12], fov: 50 }}>
            <GraphScene
              data={data}
              activeNodeFilter={activeNodeFilter}
              hiddenEdgeTypes={hiddenEdgeTypes}
            />
          </Canvas>
        )}
        {data && data.nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-text-secondary">
            No knowledge nodes yet. Start mining to build the graph.
          </div>
        )}
      </div>

      {/* Sephirot legend */}
      <div className="mt-3 flex flex-wrap gap-2">
        {Object.entries(SEPHIROT_COLORS).map(([name, color]) => (
          <span key={name} className="flex items-center gap-1 text-[10px] text-text-secondary">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: color }}
            />
            {name}
          </span>
        ))}
      </div>
    </Card>
  );
}
