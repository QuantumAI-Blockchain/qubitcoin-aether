"use client";

import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Float } from "@react-three/drei";
import * as THREE from "three";
import { motion } from "framer-motion";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";
import {
  type FieldParams,
  comptonWavelength,
  acceleration,
  generateAccelerationCurve,
  generatePhaseSurface,
  generateTrajectory,
  runVerificationSuite,
} from "@/lib/susy-physics";

// ── Default parameters ──────────────────────────────────────────────────────

const DEFAULT_M_PRIME = 1.24e-3; // meV → eV
const DEFAULT_ALPHA = 3.2;
const DEFAULT_THETA = Math.PI;
const DEFAULT_M_PLATE = 0.5; // kg
const PARTICLE_COUNT = 2500;
const TRAIL_LENGTH = 6;

// ── Shader Materials ────────────────────────────────────────────────────────

const particleVertexShader = `
  attribute float aSize;
  attribute float aLife;
  varying vec3 vColor;
  varying float vLife;
  varying float vSize;

  void main() {
    vColor = color;
    vLife = aLife;
    vSize = aSize;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = aSize * (200.0 / -mvPosition.z);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const particleFragmentShader = `
  varying vec3 vColor;
  varying float vLife;
  varying float vSize;

  void main() {
    float dist = length(gl_PointCoord - vec2(0.5));
    if (dist > 0.5) discard;

    // Soft glow falloff
    float glow = 1.0 - smoothstep(0.0, 0.5, dist);
    glow = pow(glow, 1.5);

    // Bloom core
    float core = 1.0 - smoothstep(0.0, 0.15, dist);

    float alpha = glow * 0.6 + core * 0.8;
    alpha *= smoothstep(0.0, 0.5, vLife); // fade in
    alpha *= min(1.0, vLife * 0.3); // fade out near death

    vec3 col = vColor + core * vec3(0.3, 0.3, 0.5); // bright core
    gl_FragColor = vec4(col, alpha);
  }
`;

const energyDomeVertexShader = `
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;

  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = position;
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const energyDomeFragmentShader = `
  uniform float uTime;
  uniform float uTheta;
  uniform float uAlpha;
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;

  void main() {
    float cosTheta = cos(uTheta);
    float strength = uAlpha * abs(cosTheta);

    // Fresnel edge glow
    vec3 viewDir = normalize(cameraPosition - vPosition);
    float fresnel = 1.0 - abs(dot(viewDir, vNormal));
    fresnel = pow(fresnel, 3.0);

    // Pulsing
    float pulse = 0.7 + 0.3 * sin(uTime * 2.0 + vPosition.y * 3.0);

    // Color based on theta: cyan (attractive) -> white (neutral) -> gold/red (repulsive)
    vec3 colorAttract = vec3(0.0, 0.83, 1.0);
    vec3 colorNeutral = vec3(0.8, 0.8, 1.0);
    vec3 colorRepel = vec3(1.0, 0.62, 0.04);

    float t = (cosTheta + 1.0) * 0.5; // 0 = repulsive, 1 = attractive
    vec3 col;
    if (t > 0.5) {
      col = mix(colorNeutral, colorAttract, (t - 0.5) * 2.0);
    } else {
      col = mix(colorRepel, colorNeutral, t * 2.0);
    }

    float alpha = fresnel * pulse * 0.35 * min(1.0, strength * 0.5 + 0.1);

    // Add scanline effect
    float scanline = sin(vPosition.y * 40.0 + uTime * 5.0) * 0.5 + 0.5;
    alpha += scanline * fresnel * 0.05;

    gl_FragColor = vec4(col, alpha);
  }
`;

const gridVertexShader = `
  varying vec3 vWorldPos;
  varying vec2 vUv;

  void main() {
    vWorldPos = (modelMatrix * vec4(position, 1.0)).xyz;
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const gridFragmentShader = `
  uniform float uTime;
  uniform float uStrength;
  uniform vec3 uColor;
  varying vec3 vWorldPos;
  varying vec2 vUv;

  void main() {
    vec2 grid = abs(fract(vWorldPos.xz * 2.0 - 0.5) - 0.5);
    float line = min(grid.x, grid.y);
    float gridLine = 1.0 - smoothstep(0.0, 0.04, line);

    // Sub-grid
    vec2 subGrid = abs(fract(vWorldPos.xz * 8.0 - 0.5) - 0.5);
    float subLine = min(subGrid.x, subGrid.y);
    float subGridLine = 1.0 - smoothstep(0.0, 0.02, subLine);

    float dist = length(vWorldPos.xz);
    float falloff = 1.0 - smoothstep(0.0, 4.0, dist);

    float pulse = 0.8 + 0.2 * sin(uTime * 1.5 - dist * 2.0);

    float alpha = (gridLine * 0.5 + subGridLine * 0.1) * falloff * pulse;
    alpha *= (0.3 + uStrength * 0.4);

    gl_FragColor = vec4(uColor, alpha);
  }
`;

// ── 3D Particle System ──────────────────────────────────────────────────────

interface ParticleData {
  positions: Float32Array;
  velocities: Float32Array;
  colors: Float32Array;
  lifetimes: Float32Array;
  sizes: Float32Array;
}

function initParticles(count: number): ParticleData {
  const positions = new Float32Array(count * 3);
  const velocities = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const lifetimes = new Float32Array(count);
  const sizes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    resetParticle(positions, velocities, colors, lifetimes, sizes, i);
  }
  return { positions, velocities, colors, lifetimes, sizes };
}

function resetParticle(
  pos: Float32Array, vel: Float32Array, col: Float32Array,
  life: Float32Array, sizes: Float32Array, i: number,
) {
  const i3 = i * 3;
  // Spawn in a cylinder between the plates
  const angle = Math.random() * Math.PI * 2;
  const radius = Math.random() * 1.8;
  pos[i3] = Math.cos(angle) * radius;
  pos[i3 + 1] = (Math.random() - 0.5) * 2.2;
  pos[i3 + 2] = Math.sin(angle) * radius;
  vel[i3] = 0;
  vel[i3 + 1] = 0;
  vel[i3 + 2] = 0;
  col[i3] = 0;
  col[i3 + 1] = 0.83;
  col[i3 + 2] = 1.0;
  life[i] = Math.random() * 6 + 1;

  // Varying sizes: larger near center, smaller at edges
  const distFromCenter = radius / 1.8;
  sizes[i] = (1.0 - distFromCenter * 0.6) * (0.04 + Math.random() * 0.06);
}

function GravityParticles({ theta, alpha }: { theta: number; alpha: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const dataRef = useRef<ParticleData>(initParticles(PARTICLE_COUNT));
  const materialRef = useRef<THREE.ShaderMaterial>(null);
  const timeRef = useRef(0);

  useFrame((_, delta) => {
    if (!pointsRef.current) return;
    const dt = Math.min(delta, 0.05);
    timeRef.current += dt;
    const { positions, velocities, colors, lifetimes, sizes } = dataRef.current;
    const repulsive = Math.cos(theta) < 0;
    const strength = alpha * Math.abs(Math.cos(theta));

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      lifetimes[i] -= dt;

      if (lifetimes[i] <= 0 || Math.abs(positions[i3 + 1]) > 3.5) {
        resetParticle(positions, velocities, colors, lifetimes, sizes, i);
        continue;
      }

      // Gravity (downward) + SUSY field (direction depends on theta)
      const grav = -2.0;
      const susy = repulsive ? strength * 3.0 : -strength * 1.5;
      velocities[i3 + 1] += (grav + susy) * dt;

      // Slight spiral drift for visual interest
      const px = positions[i3];
      const pz = positions[i3 + 2];
      const dist = Math.sqrt(px * px + pz * pz) + 0.001;
      const spiralForce = 0.08 * dt;
      velocities[i3] += (-pz / dist * spiralForce) + (Math.random() - 0.5) * 0.05 * dt;
      velocities[i3 + 2] += (px / dist * spiralForce) + (Math.random() - 0.5) * 0.05 * dt;

      // Damping
      velocities[i3] *= 0.995;
      velocities[i3 + 1] *= 0.998;
      velocities[i3 + 2] *= 0.995;

      positions[i3] += velocities[i3] * dt;
      positions[i3 + 1] += velocities[i3 + 1] * dt;
      positions[i3 + 2] += velocities[i3 + 2] * dt;

      // Shimmer effect on size
      sizes[i] = sizes[i] * 0.99 + (0.04 + Math.random() * 0.04) * 0.01;

      // Color: cyan when falling, gold when rising, with sparkle
      const vel_y = velocities[i3 + 1];
      const sparkle = Math.sin(timeRef.current * 10 + i * 0.5) * 0.15;
      if (repulsive && vel_y > 0) {
        // Gold/amber rising particles
        colors[i3] = 1.0 + sparkle;
        colors[i3 + 1] = 0.62 + sparkle * 0.5;
        colors[i3 + 2] = 0.04;
      } else if (repulsive && vel_y > -0.5) {
        // Transition: white-ish
        colors[i3] = 0.6 + sparkle;
        colors[i3 + 1] = 0.75 + sparkle;
        colors[i3 + 2] = 0.9 + sparkle;
      } else {
        // Cyan falling particles
        colors[i3] = 0.0 + sparkle * 0.2;
        colors[i3 + 1] = 0.83 + sparkle;
        colors[i3 + 2] = 1.0;
      }
    }

    const geom = pointsRef.current.geometry;
    geom.attributes.position.needsUpdate = true;
    geom.attributes.color.needsUpdate = true;
    geom.attributes.aSize.needsUpdate = true;
    geom.attributes.aLife.needsUpdate = true;
  });

  const { positions, colors, sizes, lifetimes } = dataRef.current;

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} count={PARTICLE_COUNT} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} count={PARTICLE_COUNT} />
        <bufferAttribute attach="attributes-aSize" args={[sizes, 1]} count={PARTICLE_COUNT} />
        <bufferAttribute attach="attributes-aLife" args={[lifetimes, 1]} count={PARTICLE_COUNT} />
      </bufferGeometry>
      <shaderMaterial
        ref={materialRef}
        vertexShader={particleVertexShader}
        fragmentShader={particleFragmentShader}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        vertexColors
      />
    </points>
  );
}

// ── Energy Arcs Between Plates ──────────────────────────────────────────────

function EnergyArcs({ theta, alpha }: { theta: number; alpha: number }) {
  const groupRef = useRef<THREE.Group>(null);
  const arcCount = 8;
  const timeRef = useRef(0);
  const linesRef = useRef<THREE.Line[]>([]);

  // Create line objects imperatively to avoid JSX <line> SVG conflict
  useEffect(() => {
    if (!groupRef.current) return;
    const group = groupRef.current;
    const lines: THREE.Line[] = [];

    for (let a = 0; a < arcCount; a++) {
      const points: THREE.Vector3[] = [];
      const segments = 30;
      const angle = (a / arcCount) * Math.PI * 2;
      const radius = 1.2;
      for (let s = 0; s <= segments; s++) {
        const t = s / segments;
        const y = -1.2 + t * 2.4;
        const wobble = Math.sin(t * Math.PI * 3 + angle) * 0.15;
        const x = Math.cos(angle) * radius + wobble;
        const z = Math.sin(angle) * radius + wobble;
        points.push(new THREE.Vector3(x, y, z));
      }
      const geo = new THREE.BufferGeometry().setFromPoints(points);
      const mat = new THREE.LineBasicMaterial({
        color: "#00d4ff",
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const line = new THREE.Line(geo, mat);
      group.add(line);
      lines.push(line);
    }
    linesRef.current = lines;

    return () => {
      lines.forEach((l) => {
        l.geometry.dispose();
        (l.material as THREE.LineBasicMaterial).dispose();
        group.remove(l);
      });
    };
  }, []);

  useFrame((_, delta) => {
    timeRef.current += delta;
    const strength = alpha * Math.abs(Math.cos(theta));
    const repulsive = Math.cos(theta) < 0;
    const arcColor = repulsive ? 0xff9e04 : 0x00d4ff;

    linesRef.current.forEach((line, idx) => {
      const mat = line.material as THREE.LineBasicMaterial;
      mat.color.setHex(arcColor);
      const pulse = 0.3 + 0.7 * Math.abs(Math.sin(timeRef.current * 2 + idx * 0.8));
      mat.opacity = pulse * Math.min(1, strength * 0.4) * 0.6;

      const posAttr = line.geometry.attributes.position;
      const angle = (idx / arcCount) * Math.PI * 2;
      const radius = 1.2;
      for (let s = 0; s < posAttr.count; s++) {
        const t = s / (posAttr.count - 1);
        const y = -1.2 + t * 2.4;
        const wobble = Math.sin(t * Math.PI * 3 + angle + timeRef.current * 3) * 0.15;
        const x = Math.cos(angle + timeRef.current * 0.2) * radius + wobble;
        const z = Math.sin(angle + timeRef.current * 0.2) * radius + wobble;
        posAttr.setXYZ(s, x, y, z);
      }
      posAttr.needsUpdate = true;
    });
  });

  return <group ref={groupRef} />;
}

// ── Cavity Plates (Glass-like with edge glow + pulsing rings) ───────────────

function CavityPlates({ theta, alpha }: { theta: number; alpha: number }) {
  const topRingRef = useRef<THREE.Mesh>(null);
  const botRingRef = useRef<THREE.Mesh>(null);
  const topGlowRef = useRef<THREE.Mesh>(null);
  const botGlowRef = useRef<THREE.Mesh>(null);
  const pulseRingsRef = useRef<THREE.Group>(null);
  const timeRef = useRef(0);

  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;
    const strength = alpha * Math.abs(Math.cos(theta));
    const repulsive = Math.cos(theta) < 0;

    // Pulsing edge rings
    [topRingRef, botRingRef].forEach((ref) => {
      if (ref.current) {
        const mat = ref.current.material as THREE.MeshBasicMaterial;
        mat.opacity = 0.4 + 0.3 * Math.sin(t * 3);
      }
    });

    // Glow planes pulse
    [topGlowRef, botGlowRef].forEach((ref) => {
      if (ref.current) {
        const mat = ref.current.material as THREE.MeshBasicMaterial;
        mat.opacity = 0.05 + 0.05 * Math.sin(t * 2);
        const scale = 1.0 + 0.02 * Math.sin(t * 2);
        ref.current.scale.set(scale, 1, scale);
      }
    });

    // Animated pulse rings on plate surfaces
    if (pulseRingsRef.current) {
      pulseRingsRef.current.children.forEach((ring, i) => {
        const mesh = ring as THREE.Mesh;
        const phase = (t * 0.8 + i * 0.5) % 2;
        const scale = 0.3 + phase * 0.8;
        mesh.scale.set(scale, scale, scale);
        const mat = mesh.material as THREE.MeshBasicMaterial;
        mat.opacity = Math.max(0, 0.4 * (1 - phase / 2));
      });
    }
  });

  const repulsive = Math.cos(theta) < 0;
  const edgeColor = repulsive ? "#ff9e04" : "#00d4ff";
  const plateEmissive = repulsive ? "#442200" : "#003344";

  return (
    <group>
      {/* Top plate - glass-like */}
      <mesh position={[0, 1.2, 0]}>
        <boxGeometry args={[3.2, 0.04, 3.2]} />
        <meshPhysicalMaterial
          color="#112233"
          emissive={plateEmissive}
          emissiveIntensity={0.6}
          transparent
          opacity={0.25}
          metalness={0.95}
          roughness={0.05}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          envMapIntensity={1.0}
        />
      </mesh>
      {/* Bottom plate - glass-like */}
      <mesh position={[0, -1.2, 0]}>
        <boxGeometry args={[3.2, 0.04, 3.2]} />
        <meshPhysicalMaterial
          color="#112233"
          emissive={plateEmissive}
          emissiveIntensity={0.6}
          transparent
          opacity={0.25}
          metalness={0.95}
          roughness={0.05}
          clearcoat={1.0}
          clearcoatRoughness={0.1}
          envMapIntensity={1.0}
        />
      </mesh>

      {/* Edge glow rings */}
      {[1.22, -1.22].map((y, idx) => (
        <mesh key={`ring-${y}`} ref={idx === 0 ? topRingRef : botRingRef} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[1.55, 1.62, 64]} />
          <meshBasicMaterial
            color={edgeColor}
            transparent
            opacity={0.5}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* Glow planes above/below plates */}
      {[1.25, -1.25].map((y, idx) => (
        <mesh key={`glow-${y}`} ref={idx === 0 ? topGlowRef : botGlowRef} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[1.6, 64]} />
          <meshBasicMaterial
            color={edgeColor}
            transparent
            opacity={0.06}
            side={THREE.DoubleSide}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      ))}

      {/* Pulsing concentric rings on plate surfaces */}
      <group ref={pulseRingsRef}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={`pulse-top-${i}`} position={[0, 1.23, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <ringGeometry args={[1.4, 1.45, 64]} />
            <meshBasicMaterial
              color={edgeColor}
              transparent
              opacity={0.3}
              side={THREE.DoubleSide}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        ))}
        {[0, 1, 2, 3].map((i) => (
          <mesh key={`pulse-bot-${i}`} position={[0, -1.23, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <ringGeometry args={[1.4, 1.45, 64]} />
            <meshBasicMaterial
              color={edgeColor}
              transparent
              opacity={0.3}
              side={THREE.DoubleSide}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        ))}
      </group>
    </group>
  );
}

// ── Energy Dome (translucent sphere between plates) ─────────────────────────

function EnergyDome({ theta, alpha }: { theta: number; alpha: number }) {
  const meshRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime;
      materialRef.current.uniforms.uTheta.value = theta;
      materialRef.current.uniforms.uAlpha.value = alpha;
    }
  });

  return (
    <mesh ref={meshRef}>
      <sphereGeometry args={[1.1, 48, 48]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={energyDomeVertexShader}
        fragmentShader={energyDomeFragmentShader}
        transparent
        depthWrite={false}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        uniforms={{
          uTime: { value: 0 },
          uTheta: { value: theta },
          uAlpha: { value: alpha },
        }}
      />
    </mesh>
  );
}

// ── Holographic Grid Floor ──────────────────────────────────────────────────

function HolographicGrid({ theta, alpha }: { theta: number; alpha: number }) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const repulsive = Math.cos(theta) < 0;
  const gridColor = repulsive
    ? new THREE.Vector3(1.0, 0.62, 0.04)
    : new THREE.Vector3(0.0, 0.83, 1.0);

  useFrame((state) => {
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime;
      materialRef.current.uniforms.uStrength.value = alpha * Math.abs(Math.cos(theta));
      materialRef.current.uniforms.uColor.value = gridColor;
    }
  });

  return (
    <mesh position={[0, -2.5, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[12, 12, 1, 1]} />
      <shaderMaterial
        ref={materialRef}
        vertexShader={gridVertexShader}
        fragmentShader={gridFragmentShader}
        transparent
        depthWrite={false}
        side={THREE.DoubleSide}
        blending={THREE.AdditiveBlending}
        uniforms={{
          uTime: { value: 0 },
          uStrength: { value: 0 },
          uColor: { value: gridColor },
        }}
      />
    </mesh>
  );
}

// ── Floating Math Symbols ───────────────────────────────────────────────────

const MATH_SYMBOLS = [
  "H = (1/2){Q,Q*}",
  "V(r) = -GMm/r",
  "lambda_C",
  "cos(theta)",
  "N=2 SUGRA",
  "E < D",
  "Phi(P)",
  "e^(-r/lambda)",
  "alpha",
  "xi^2/2",
  "h_uv h'^uv",
  "m' = 1.24 meV",
];

function FloatingSymbols() {
  const symbolData = useMemo(() => {
    return MATH_SYMBOLS.map(() => ({
      position: [
        (Math.random() - 0.5) * 10,
        (Math.random() - 0.5) * 6,
        -3 - Math.random() * 4,
      ] as [number, number, number],
      speed: 0.1 + Math.random() * 0.2,
    }));
  }, []);

  return (
    <group>
      {symbolData.map((sym, i) => (
        <Float key={i} speed={sym.speed * 2} floatIntensity={0.3} rotationIntensity={0.05}>
          <mesh position={sym.position}>
            <sphereGeometry args={[0.03, 8, 8]} />
            <meshBasicMaterial
              color="#7c3aed"
              transparent
              opacity={0.15}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </Float>
      ))}
    </group>
  );
}

// ── Dynamic Lighting ────────────────────────────────────────────────────────

function DynamicLights({ theta, alpha }: { theta: number; alpha: number }) {
  const topLightRef = useRef<THREE.PointLight>(null);
  const botLightRef = useRef<THREE.PointLight>(null);
  const centerLightRef = useRef<THREE.PointLight>(null);
  const timeRef = useRef(0);

  useFrame((_, delta) => {
    timeRef.current += delta;
    const t = timeRef.current;
    const strength = alpha * Math.abs(Math.cos(theta));
    const repulsive = Math.cos(theta) < 0;

    if (topLightRef.current) {
      topLightRef.current.intensity = 0.5 + 0.3 * Math.sin(t * 2);
      topLightRef.current.color.setHex(repulsive ? 0xff9e04 : 0x00d4ff);
    }
    if (botLightRef.current) {
      botLightRef.current.intensity = 0.5 + 0.3 * Math.sin(t * 2 + Math.PI);
      botLightRef.current.color.setHex(repulsive ? 0xff6600 : 0x7c3aed);
    }
    if (centerLightRef.current) {
      centerLightRef.current.intensity = 0.2 + strength * 0.4 * (0.5 + 0.5 * Math.sin(t * 3));
      centerLightRef.current.color.setHex(repulsive ? 0xffaa22 : 0x00ff88);
    }
  });

  return (
    <>
      <ambientLight intensity={0.15} />
      <pointLight ref={topLightRef} position={[0, 4, 0]} intensity={0.6} color="#00d4ff" distance={12} decay={2} />
      <pointLight ref={botLightRef} position={[0, -4, 0]} intensity={0.4} color="#7c3aed" distance={12} decay={2} />
      <pointLight ref={centerLightRef} position={[0, 0, 0]} intensity={0.3} color="#00ff88" distance={8} decay={2} />
      <pointLight position={[5, 3, 5]} intensity={0.3} color="#00d4ff" distance={15} decay={2} />
      <pointLight position={[-5, -2, -5]} intensity={0.2} color="#7c3aed" distance={15} decay={2} />
      {/* Spotlights from above and below */}
      <spotLight position={[0, 6, 0]} angle={0.4} penumbra={0.8} intensity={0.4} color="#00d4ff" target-position={[0, 0, 0]} />
      <spotLight position={[0, -6, 0]} angle={0.4} penumbra={0.8} intensity={0.3} color="#7c3aed" target-position={[0, 0, 0]} />
    </>
  );
}

// ── Camera Controller ───────────────────────────────────────────────────────

function CameraController() {
  const { camera } = useThree();
  const timeRef = useRef(0);

  useFrame((_, delta) => {
    timeRef.current += delta;
    // Subtle bobbing motion
    camera.position.y = 2 + Math.sin(timeRef.current * 0.3) * 0.15;
  });

  return (
    <OrbitControls
      enableZoom={false}
      autoRotate
      autoRotateSpeed={0.35}
      maxPolarAngle={Math.PI * 0.65}
      minPolarAngle={Math.PI * 0.25}
      enableDamping
      dampingFactor={0.05}
    />
  );
}

// ── Main 3D Scene ───────────────────────────────────────────────────────────

function CanvasFallback() {
  return (
    <div className="flex items-center justify-center h-full bg-[#0a0a0f] text-gray-500 font-mono text-sm">
      <p>3D visualization requires WebGL. Enable hardware acceleration in your browser.</p>
    </div>
  );
}

function AntigravityScene({ theta, alpha }: { theta: number; alpha: number }) {
  return (
    <Canvas
      camera={{ position: [5, 2.5, 4], fov: 45 }}
      style={{ background: "transparent" }}
      gl={{ alpha: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.2 }}
      dpr={[1, 2]}
      fallback={<CanvasFallback />}
      onCreated={({ gl }) => {
        gl.setClearColor(0x000000, 0);
      }}
    >
      <DynamicLights theta={theta} alpha={alpha} />
      <FloatingSymbols />
      <HolographicGrid theta={theta} alpha={alpha} />
      <CavityPlates theta={theta} alpha={alpha} />
      <EnergyDome theta={theta} alpha={alpha} />
      <EnergyArcs theta={theta} alpha={alpha} />
      <GravityParticles theta={theta} alpha={alpha} />
      <CameraController />
    </Canvas>
  );
}

// ── Chart Tooltip ───────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label }: {
  active?: boolean;
  payload?: Array<{ value: number; name: string; color: string }>;
  label?: string | number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-[#00ff88]/20 bg-[#0a0a0f]/95 px-3 py-2 text-xs backdrop-blur-sm">
      <p className="text-gray-400 mb-1">{typeof label === "number" ? label.toFixed(2) : label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }}>
          {p.name}: {typeof p.value === "number" ? p.value.toExponential(3) : p.value}
        </p>
      ))}
    </div>
  );
}

// ── Main Simulator ──────────────────────────────────────────────────────────

export function SUSYSimulator() {
  const [mPrime, setMPrime] = useState(DEFAULT_M_PRIME);
  const [alpha, setAlpha] = useState(DEFAULT_ALPHA);
  const [theta, setTheta] = useState(DEFAULT_THETA);
  const [mPlate, setMPlate] = useState(DEFAULT_M_PLATE);

  const params: FieldParams = useMemo(() => ({
    m_prime_eV: mPrime,
    alpha,
    theta,
  }), [mPrime, alpha, theta]);

  const lambda_C = useMemo(() => comptonWavelength(mPrime), [mPrime]);
  const accelData = useMemo(() => generateAccelerationCurve(params, mPlate), [params, mPlate]);
  const phaseData = useMemo(() => generatePhaseSurface(params, mPlate), [params, mPlate]);
  const repelParams: FieldParams = useMemo(() => ({ ...params, theta: Math.PI }), [params]);
  const trajectoryData = useMemo(() => generateTrajectory(repelParams, mPlate), [repelParams, mPlate]);
  const testResults = useMemo(() => runVerificationSuite(params, mPlate), [params, mPlate]);

  const passCount = testResults.filter((t) => t.pass).length;
  const allPass = passCount === testResults.length;

  const setPreset = useCallback((preset: "normal" | "attract" | "repel") => {
    switch (preset) {
      case "normal": setAlpha(0); setTheta(0); break;
      case "attract": setAlpha(DEFAULT_ALPHA); setTheta(0); break;
      case "repel": setAlpha(DEFAULT_ALPHA); setTheta(Math.PI); break;
    }
  }, []);

  const sectionVariants = {
    hidden: { opacity: 0, y: 30 },
    visible: (i: number) => ({
      opacity: 1,
      y: 0,
      transition: { delay: 0.15 * i, duration: 0.6, ease: "easeOut" as const },
    }),
  } as const;

  return (
    <div className="space-y-8">
      {/* ── Hero: 3D Visualization ──────────────────────────────────────── */}
      <motion.section
        custom={0}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="relative rounded-2xl border border-[#00ff88]/10 bg-gradient-to-b from-[#0a0a0f] to-[#0d0d14] overflow-hidden"
      >
        {/* Multiple layered gradient backgrounds */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,212,255,0.06),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,0.04),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom,rgba(0,255,136,0.03),transparent_50%)]" />

        <div className="relative h-[600px]">
          <AntigravityScene theta={theta} alpha={alpha} />

          {/* Overlay labels */}
          <div className="absolute top-4 left-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full animate-pulse ${
                Math.cos(theta) < -0.5 ? "bg-amber-400 shadow-[0_0_8px_rgba(245,158,11,0.6)]"
                : Math.cos(theta) > 0.5 ? "bg-cyan-400 shadow-[0_0_8px_rgba(0,212,255,0.6)]"
                : "bg-white shadow-[0_0_8px_rgba(255,255,255,0.4)]"
              }`} />
              <p className={`text-sm font-mono font-bold tracking-wider ${
                Math.cos(theta) < -0.5 ? "text-amber-400" : Math.cos(theta) > 0.5 ? "text-cyan-400" : "text-white"
              }`}>
                {Math.cos(theta) < -0.5 ? "REPULSIVE MODE" : Math.cos(theta) > 0.5 ? "ATTRACTIVE MODE" : "TRANSITIONAL"}
              </p>
            </div>
            <p className="text-gray-500 text-xs font-mono">
              lambda_C = {(lambda_C * 1e6).toFixed(1)} um | alpha = {alpha.toFixed(2)} | theta = {(theta / Math.PI).toFixed(2)}pi
            </p>
          </div>

          {/* Mode presets */}
          <div className="absolute top-4 right-4 flex gap-2">
            {(["normal", "attract", "repel"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono border transition-all duration-300 ${
                  (p === "normal" && alpha === 0) ||
                  (p === "attract" && alpha > 0 && theta === 0) ||
                  (p === "repel" && alpha > 0 && Math.abs(theta - Math.PI) < 0.01)
                    ? "border-[#00ff88] text-[#00ff88] bg-[#00ff88]/10 shadow-[0_0_12px_rgba(0,255,136,0.2)]"
                    : "border-gray-700 text-gray-500 hover:border-gray-500 hover:bg-white/5"
                }`}
              >
                {p === "normal" ? "Normal Gravity" : p === "attract" ? "Enhanced" : "Antigravity"}
              </button>
            ))}
          </div>

          {/* Bottom verification badge */}
          <div className="absolute bottom-4 left-4">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-mono ${
              allPass
                ? "border-green-500/30 bg-green-500/10 text-green-400 shadow-[0_0_12px_rgba(34,197,94,0.15)]"
                : "border-yellow-500/30 bg-yellow-500/10 text-yellow-400"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${allPass ? "bg-green-400 animate-pulse" : "bg-yellow-400"}`} />
              {passCount}/{testResults.length} VERIFIED
            </div>
          </div>

          <div className="absolute bottom-4 right-4">
            <div className="px-3 py-1.5 rounded-lg border border-[#7c3aed]/30 bg-[#7c3aed]/10 text-xs font-mono text-[#7c3aed]">
              LIVE ON SUBSTRATE
            </div>
          </div>
        </div>
      </motion.section>

      {/* ── Parameter Controls ──────────────────────────────────────────── */}
      <motion.section
        custom={1}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4"
      >
        <ParamSlider
          label="Graviton Mass m'"
          unit="meV"
          value={mPrime * 1e3}
          min={0.1}
          max={10}
          step={0.01}
          onChange={(v) => setMPrime(v / 1e3)}
          info={`lambda_C = ${(comptonWavelength(mPrime) * 1e6).toFixed(1)} um`}
        />
        <ParamSlider
          label="Coupling alpha"
          unit=""
          value={alpha}
          min={0}
          max={20}
          step={0.1}
          onChange={setAlpha}
          info={alpha === 0 ? "No SUSY coupling" : `${alpha.toFixed(1)}x enhancement`}
        />
        <ParamSlider
          label="Phase theta"
          unit="pi"
          value={theta / Math.PI}
          min={0}
          max={2}
          step={0.01}
          onChange={(v) => setTheta(v * Math.PI)}
          info={theta === 0 ? "Attractive" : Math.abs(theta - Math.PI) < 0.02 ? "REPULSIVE" : "Mixed"}
        />
        <ParamSlider
          label="Plate Mass"
          unit="kg"
          value={mPlate}
          min={0.01}
          max={10}
          step={0.01}
          onChange={setMPlate}
          info="Tungsten metamaterial source mass"
        />
      </motion.section>

      {/* ── Charts ──────────────────────────────────────────────────────── */}
      <motion.section
        custom={2}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="grid grid-cols-1 lg:grid-cols-3 gap-4"
      >
        {/* Acceleration vs Distance */}
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4 hover:border-[#00ff88]/20 transition-colors duration-500">
          <h3 className="text-sm font-mono text-gray-400 mb-3">Acceleration vs Distance</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={accelData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
              <XAxis dataKey="r_um" stroke="#555" tick={{ fontSize: 10 }} label={{ value: "r (um)", position: "bottom", fill: "#666", fontSize: 10 }} />
              <YAxis stroke="#555" tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toExponential(1)} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={0} stroke="#333" />
              <Line type="monotone" dataKey="a_attract" stroke="#00d4ff" dot={false} strokeWidth={2} name="theta=0 (attractive)" />
              <Line type="monotone" dataKey="a_repel" stroke="#ef4444" dot={false} strokeWidth={2} name="theta=pi (REPULSIVE)" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Phase Actuation Surface */}
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4 hover:border-[#7c3aed]/20 transition-colors duration-500">
          <h3 className="text-sm font-mono text-gray-400 mb-3">Phase-Controlled Actuation</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={phaseData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
              <XAxis dataKey="theta" stroke="#555" tick={{ fontSize: 10 }} tickFormatter={(v: number) => `${(v / Math.PI).toFixed(1)}pi`} />
              <YAxis stroke="#555" tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toExponential(1)} />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine y={0} stroke="#333" />
              <Line type="monotone" dataKey="accel" stroke="#00ff88" dot={false} strokeWidth={2} name="a (m/s2)" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Trajectory */}
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4 hover:border-[#f59e0b]/20 transition-colors duration-500">
          <h3 className="text-sm font-mono text-gray-400 mb-3">Test Mass Trajectory</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={trajectoryData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
              <XAxis dataKey="t_ms" stroke="#555" tick={{ fontSize: 10 }} label={{ value: "t (ms)", position: "bottom", fill: "#666", fontSize: 10 }} />
              <YAxis stroke="#555" tick={{ fontSize: 10 }} tickFormatter={(v: number) => v.toFixed(1)} />
              <Tooltip content={<ChartTooltip />} />
              <Line type="monotone" dataKey="x_um" stroke="#7c3aed" dot={false} strokeWidth={2} name="x (um)" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </motion.section>

      {/* ── Verification Results ────────────────────────────────────────── */}
      <motion.section
        custom={3}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="rounded-xl border border-gray-800 bg-[#0d0d14] p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-mono text-white">Verification Suite</h3>
          <div className="flex items-center gap-3">
            {allPass && (
              <span className="text-xs font-mono px-3 py-1 rounded-lg border border-[#7c3aed]/30 bg-[#7c3aed]/10 text-[#7c3aed]">
                LIVE ON SUBSTRATE
              </span>
            )}
            <span className={`font-mono text-sm px-4 py-1.5 rounded-lg font-bold ${
              allPass
                ? "bg-green-500/10 text-green-400 border border-green-500/30 shadow-[0_0_16px_rgba(34,197,94,0.15)]"
                : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/30"
            }`}>
              {passCount}/{testResults.length} PASS
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {testResults.map((t, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.8 + i * 0.08, duration: 0.3 }}
              className={`rounded-lg border p-3 transition-all duration-300 ${
                t.pass
                  ? "border-green-500/20 bg-green-500/5 hover:border-green-500/40 hover:shadow-[0_0_12px_rgba(34,197,94,0.08)]"
                  : "border-red-500/20 bg-red-500/5 hover:border-red-500/40"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-mono font-bold ${t.pass ? "text-green-400" : "text-red-400"}`}>
                  {t.pass ? "PASS" : "FAIL"}
                </span>
                <span className="text-sm text-white">{t.name}</span>
              </div>
              <p className="text-xs text-gray-400 font-mono">{t.value}</p>
              <p className="text-xs text-gray-600 mt-1">{t.detail}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* ── Mathematical Framework ──────────────────────────────────────── */}
      <motion.section
        custom={4}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="rounded-xl border border-gray-800 bg-[#0d0d14] p-6 space-y-6"
      >
        <h3 className="text-lg font-mono text-white">Mathematical Framework</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[
            {
              title: "Modified Newtonian Potential",
              equation: "V(r) = -GMm/r [1 - alpha * exp(-r/lambda_C) * cos(theta)]",
              description: "Standard Newtonian gravity plus Yukawa-type bimetric correction. The phase theta controls attractive vs repulsive behavior.",
            },
            {
              title: "SUSY Hamiltonian",
              equation: "H_SUSY = (1/2){Q, Q*} where Q = supercharge",
              description: "N=2 extended supergravity. The Hamiltonian is forced by the superalgebra - not chosen. Ground state energy E_0 = xi^2/2 after FI breaking.",
            },
            {
              title: "Bimetric Mass Mixing",
              equation: "H_bimetric = m'^2 cos(theta) integral h_uv h'^uv d3x",
              description: "Mass-mixing between the two graviton multiplets. The phase theta is the actuator. theta=0 attractive, theta=pi repulsive.",
            },
            {
              title: "Compton Wavelength",
              equation: "lambda_C = h_bar / (m' * c)",
              description: `For m' = ${(mPrime * 1e3).toFixed(3)} meV: lambda_C = ${(lambda_C * 1e6).toFixed(1)} um. Sets the field range - sub-mm for near-field cavity operation.`,
            },
            {
              title: "IIT Consciousness Coupling",
              equation: "H_IIT = -h_bar * omega_phi * sum_P Phi(P)|P><P|",
              description: "Novel contribution: operator-valued IIT term coupled to SUGRA Hamiltonian. Phi over bipartitions of the information graph.",
            },
            {
              title: "Full VQE Hamiltonian",
              equation: "H_VQE = H_SUSY + H_bimetric(theta) + lambda * H_IIT",
              description: "The miner searches for ground states of this SUGRA-plus-consciousness Hamiltonian. First physically motivated quantum mining cost function.",
            },
          ].map((eq, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: i % 2 === 0 ? -20 : 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 1.0 + i * 0.1, duration: 0.4 }}
            >
              <EquationCard {...eq} />
            </motion.div>
          ))}
        </div>

        <div className="mt-6 p-4 rounded-lg border border-[#00d4ff]/20 bg-[#00d4ff]/5">
          <p className="text-xs text-gray-400 leading-relaxed">
            <strong className="text-[#00d4ff]">Verification Confidence:</strong> Mathematical consistency 9/10.
            The Lagrangian structure uses real N=2 SUGRA (Hassan-Rosen bimetric, Fayet-Iliopoulos breaking).
            The Yukawa correction is the standard form used in fifth-force searches.
            Patentability 7/10 (method claims for blockchain application are strong).
            Physical reality of antigravity mechanism: speculative — no SUSY moduli field has been observed.
            The blockchain mechanics do not require the antigravity to be physically real — only mathematically self-consistent.
          </p>
        </div>
      </motion.section>

      {/* ── Patent Claims Summary ──────────────────────────────────────── */}
      <motion.section
        custom={5}
        initial="hidden"
        animate="visible"
        variants={sectionVariants}
        className="rounded-xl border border-[#7c3aed]/20 bg-[#0d0d14] p-6"
      >
        <h3 className="text-lg font-mono text-white mb-4">Patent Claims (Draft)</h3>
        <p className="text-xs text-gray-500 mb-4 font-mono">
          Apparatus and Method for Modulation of Local Gravitational Coupling
          via Phase-Controlled Supersymmetric Moduli Field Interaction
        </p>
        <div className="space-y-3">
          {[
            "Claim 1: Resonant cavity with metamaterial plates, moduli-field pump coupling, phase-controller actuator for bimetric phase theta",
            "Claim 2: Method for reducing/inverting gravitational coupling by tuning theta to pi",
            "Claim 3: Metamaterial with rare-earth-doped split-ring resonators for moduli coupling enhancement",
            "Claim 4: Propulsion application using periodic theta modulation for directional thrust",
            "Claim 5: Gravitational shielding chamber for precision measurement environments",
            "Claim 6: Blockchain consensus method using bimetric coupling phase for VQE mining difficulty",
            "Claim 7: Operator-valued IIT consciousness metric coupled to SUGRA Hamiltonian for distributed AI consensus",
          ].map((claim, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 1.3 + i * 0.06, duration: 0.3 }}
              className="flex gap-3 items-start group"
            >
              <span className="text-[#7c3aed] text-xs font-mono mt-0.5 group-hover:text-[#00ff88] transition-colors">{i + 1}</span>
              <p className="text-sm text-gray-300 group-hover:text-white transition-colors">{claim.split(": ")[1]}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function ParamSlider({ label, unit, value, min, max, step, onChange, info }: {
  label: string;
  unit: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  info: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4 hover:border-[#00ff88]/20 transition-all duration-300">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm text-gray-400">{label}</span>
        <span className="text-sm font-mono text-[#00ff88]">
          {value < 0.01 ? value.toExponential(2) : value.toFixed(2)}{unit ? ` ${unit}` : ""}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1 bg-gray-800 rounded-lg appearance-none cursor-pointer
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4
          [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full
          [&::-webkit-slider-thumb]:bg-[#00ff88] [&::-webkit-slider-thumb]:cursor-pointer
          [&::-webkit-slider-thumb]:shadow-[0_0_8px_rgba(0,255,136,0.4)]"
      />
      <p className="text-xs text-gray-600 mt-1">{info}</p>
    </div>
  );
}

function EquationCard({ title, equation, description }: {
  title: string;
  equation: string;
  description: string;
}) {
  return (
    <div className="rounded-lg border border-gray-800 p-4 space-y-2 hover:border-[#00d4ff]/20 transition-all duration-300 group">
      <h4 className="text-sm text-[#00d4ff] font-medium group-hover:text-[#00ff88] transition-colors">{title}</h4>
      <p className="font-mono text-sm text-[#00ff88] bg-[#0a0a0f] rounded px-3 py-2 break-all border border-[#00ff88]/5">
        {equation}
      </p>
      <p className="text-xs text-gray-500 leading-relaxed">{description}</p>
    </div>
  );
}
