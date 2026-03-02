"use client";

import { useRef, useMemo, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

const PHI = 1.618033988749895;
const TAU = Math.PI * 2;

// --- Custom shader: quantum probability particles with glow halos ---
const quantumVertexShader = `
  #define TAU 6.2831853071795864

  attribute float aPhase;
  attribute float aEnergy;
  attribute float aEntangled;
  attribute vec3 aGhost;

  varying float vPhase;
  varying float vEnergy;
  varying float vEntangled;
  varying vec3 vColor;

  uniform float uTime;
  uniform float uCollapse;

  void main() {
    vPhase = aPhase;
    vEnergy = aEnergy;
    vEntangled = aEntangled;
    vColor = color;

    // Superposition: particle oscillates between real position and ghost position
    float collapseWave = sin(uTime * 0.7 + aPhase * 6.2831) * 0.5 + 0.5;
    float superpositionMix = smoothstep(0.3, 0.7, collapseWave) * (1.0 - uCollapse);
    vec3 pos = mix(position, aGhost, superpositionMix * 0.4);

    // Quantum jitter — Heisenberg uncertainty
    float uncertainty = aEnergy * 0.03;
    pos.x += sin(uTime * 3.7 + aPhase * 17.0) * uncertainty;
    pos.y += cos(uTime * 2.9 + aPhase * 13.0) * uncertainty;
    pos.z += sin(uTime * 4.3 + aPhase * 23.0) * uncertainty;

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);

    // Size pulses with energy level — discrete quantum steps
    float energyStep = floor(aEnergy * 4.0) / 4.0;
    float pulse = 1.0 + sin(uTime * (1.0 + energyStep * 2.0) + aPhase * TAU) * 0.3;
    gl_PointSize = (1.5 + energyStep * 1.5) * pulse * (300.0 / -mvPosition.z);

    gl_Position = projectionMatrix * mvPosition;
  }
`;

const quantumFragmentShader = `
  varying float vPhase;
  varying float vEnergy;
  varying float vEntangled;
  varying vec3 vColor;

  uniform float uTime;

  void main() {
    vec2 center = gl_PointCoord - 0.5;
    float dist = length(center);

    // Discard outside circle
    if (dist > 0.5) discard;

    // Core glow — sharp bright center
    float core = exp(-dist * 12.0);

    // Probability cloud — soft outer halo
    float halo = exp(-dist * 4.0) * 0.4;

    // Interference rings for entangled particles
    float rings = 0.0;
    if (vEntangled > 0.5) {
      rings = sin(dist * 25.0 - uTime * 3.0) * 0.15 * exp(-dist * 6.0);
    }

    // Wave function shimmer
    float shimmer = sin(dist * 15.0 + uTime * 2.0 + vPhase * 6.2831) * 0.08 * exp(-dist * 5.0);

    float alpha = core + halo + rings + shimmer;
    alpha *= 0.7 + vEnergy * 0.3;

    // Color shift based on energy state
    vec3 col = vColor;
    col += vec3(0.1, 0.15, 0.3) * rings;
    col += vec3(shimmer * 0.5);

    gl_FragColor = vec4(col, alpha);
  }
`;

// --- Entanglement filament shader ---
const filamentVertexShader = `
  attribute float aProgress;
  attribute float aPairId;

  varying float vProgress;
  varying float vPairId;

  uniform float uTime;

  void main() {
    vProgress = aProgress;
    vPairId = aPairId;

    vec3 pos = position;

    // Lateral wave along the filament
    float wave = sin(aProgress * 12.566 + uTime * 2.0 + aPairId * 3.0) * 0.06;
    pos.y += wave;
    pos.x += cos(aProgress * 12.566 + uTime * 1.5 + aPairId * 5.0) * 0.04;

    vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mvPosition;
  }
`;

const filamentFragmentShader = `
  varying float vProgress;
  varying float vPairId;

  uniform float uTime;

  void main() {
    // Traveling pulse along the filament
    float pulse = sin(vProgress * 6.2831 * 3.0 - uTime * 4.0 + vPairId * 2.0);
    pulse = smoothstep(0.3, 1.0, pulse);

    // Fade at endpoints
    float endFade = smoothstep(0.0, 0.1, vProgress) * smoothstep(1.0, 0.9, vProgress);

    // Color: cyan ↔ violet based on pulse
    vec3 cyan = vec3(0.0, 0.83, 1.0);
    vec3 violet = vec3(0.486, 0.227, 0.929);
    vec3 col = mix(cyan, violet, pulse);

    float alpha = (0.08 + pulse * 0.15) * endFade;

    gl_FragColor = vec4(col, alpha);
  }
`;

const TAU_CONST = Math.PI * 2;

// ============================================================
// Main quantum particle system
// ============================================================
function QuantumParticles() {
  const pointsRef = useRef<THREE.Points>(null);
  const filamentRef = useRef<THREE.LineSegments>(null);
  const uniforms = useRef({
    uTime: { value: 0 },
    uCollapse: { value: 0 },
  });
  const filamentUniforms = useRef({
    uTime: { value: 0 },
  });

  const PARTICLE_COUNT = 600;
  const ENTANGLED_PAIRS = 40;
  const FILAMENT_SEGMENTS = 24;

  const { positions, ghosts, phases, energies, entangled, colors } = useMemo(() => {
    const pos = new Float32Array(PARTICLE_COUNT * 3);
    const gho = new Float32Array(PARTICLE_COUNT * 3);
    const pha = new Float32Array(PARTICLE_COUNT);
    const ene = new Float32Array(PARTICLE_COUNT);
    const ent = new Float32Array(PARTICLE_COUNT);
    const col = new Float32Array(PARTICLE_COUNT * 3);

    const cyan = new THREE.Color("#00d4ff");
    const violet = new THREE.Color("#7c3aed");
    const gold = new THREE.Color("#f59e0b");

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const phase = i / PARTICLE_COUNT;
      pha[i] = phase;

      // Energy quantized to discrete levels (like real quantum states)
      ene[i] = Math.floor(Math.random() * 5) / 4;

      // Phi-spiral with multiple arms, discrete orbital shells — spread wide
      const shell = Math.floor(Math.random() * 7);
      const shellRadius = (shell + 1) * 2.5;
      const arm = i % 3;
      const armOffset = (arm / 3) * TAU_CONST;
      const angle = phase * TAU_CONST * 8 * PHI + armOffset;

      const spread = 1.0 + shell * 0.5;
      pos[i * 3] = Math.cos(angle) * shellRadius + (Math.random() - 0.5) * spread;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 8;
      pos[i * 3 + 2] = Math.sin(angle) * shellRadius * 0.3 + (Math.random() - 0.5) * spread * 0.5;

      // Ghost position (superposition alternate) — mirrored through origin with offset
      gho[i * 3] = -pos[i * 3] * 0.6 + (Math.random() - 0.5) * 4;
      gho[i * 3 + 1] = pos[i * 3 + 1] * 0.8 + (Math.random() - 0.5) * 3;
      gho[i * 3 + 2] = -pos[i * 3 + 2] * 0.6 + (Math.random() - 0.5) * 1;

      ent[i] = 0;

      // Color by energy level: low=cyan, mid=violet, high=gold
      const t = ene[i];
      const c = new THREE.Color();
      if (t < 0.5) {
        c.lerpColors(cyan, violet, t * 2);
      } else {
        c.lerpColors(violet, gold, (t - 0.5) * 2);
      }
      col[i * 3] = c.r;
      col[i * 3 + 1] = c.g;
      col[i * 3 + 2] = c.b;
    }

    // Mark entangled pairs
    for (let p = 0; p < ENTANGLED_PAIRS; p++) {
      const a = Math.floor(Math.random() * PARTICLE_COUNT);
      const b = Math.floor(Math.random() * PARTICLE_COUNT);
      ent[a] = 1;
      ent[b] = 1;
    }

    return { positions: pos, ghosts: gho, phases: pha, energies: ene, entangled: ent, colors: col };
  }, [PARTICLE_COUNT, ENTANGLED_PAIRS]);

  // Entanglement filament geometry — lines connecting entangled pairs
  const { filamentPositions, filamentProgress, filamentPairIds } = useMemo(() => {
    const totalVerts = ENTANGLED_PAIRS * FILAMENT_SEGMENTS * 2;
    const fPos = new Float32Array(totalVerts * 3);
    const fProg = new Float32Array(totalVerts);
    const fPairId = new Float32Array(totalVerts);

    // Find entangled particles
    const entangledIndices: number[] = [];
    for (let i = 0; i < PARTICLE_COUNT; i++) {
      if (entangled[i] > 0.5) entangledIndices.push(i);
    }

    for (let p = 0; p < ENTANGLED_PAIRS; p++) {
      const aIdx = entangledIndices[p % entangledIndices.length];
      const bIdx = entangledIndices[(p + ENTANGLED_PAIRS) % entangledIndices.length];

      const ax = positions[aIdx * 3], ay = positions[aIdx * 3 + 1], az = positions[aIdx * 3 + 2];
      const bx = positions[bIdx * 3], by = positions[bIdx * 3 + 1], bz = positions[bIdx * 3 + 2];

      for (let s = 0; s < FILAMENT_SEGMENTS; s++) {
        const t0 = s / FILAMENT_SEGMENTS;
        const t1 = (s + 1) / FILAMENT_SEGMENTS;
        const vi = (p * FILAMENT_SEGMENTS + s) * 2;

        // Interpolate with a slight arc
        const mid = 0.5;
        const arcY0 = Math.sin(t0 * Math.PI) * 0.5;
        const arcY1 = Math.sin(t1 * Math.PI) * 0.5;

        fPos[vi * 3] = ax + (bx - ax) * t0;
        fPos[vi * 3 + 1] = ay + (by - ay) * t0 + arcY0;
        fPos[vi * 3 + 2] = az + (bz - az) * t0;

        fPos[(vi + 1) * 3] = ax + (bx - ax) * t1;
        fPos[(vi + 1) * 3 + 1] = ay + (by - ay) * t1 + arcY1;
        fPos[(vi + 1) * 3 + 2] = az + (bz - az) * t1;

        fProg[vi] = t0;
        fProg[vi + 1] = t1;
        fPairId[vi] = p;
        fPairId[vi + 1] = p;
      }
    }

    return { filamentPositions: fPos, filamentProgress: fProg, filamentPairIds: fPairId };
  }, [positions, entangled, ENTANGLED_PAIRS, FILAMENT_SEGMENTS, PARTICLE_COUNT]);

  // Orbital drift — particles slowly orbit their shell
  const basePositions = useRef(new Float32Array(positions));

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    uniforms.current.uTime.value = t;
    filamentUniforms.current.uTime.value = t;

    // Collapse wave — periodic moments of "measurement"
    const collapseFreq = 0.15;
    const collapseWave = Math.pow(Math.sin(t * collapseFreq) * 0.5 + 0.5, 8);
    uniforms.current.uCollapse.value = collapseWave;

    // Orbital motion
    if (pointsRef.current) {
      const posArr = pointsRef.current.geometry.attributes.position.array as Float32Array;
      const base = basePositions.current;

      for (let i = 0; i < PARTICLE_COUNT; i++) {
        const bx = base[i * 3];
        const bz = base[i * 3 + 2];
        const r = Math.sqrt(bx * bx + bz * bz);
        if (r < 0.01) continue;

        // Orbital speed inversely proportional to shell radius (Kepler-like)
        const speed = 0.02 / (1 + r * 0.1);
        const angle = Math.atan2(bz, bx) + t * speed;

        posArr[i * 3] = Math.cos(angle) * r;
        posArr[i * 3 + 2] = Math.sin(angle) * r;
      }

      pointsRef.current.geometry.attributes.position.needsUpdate = true;
    }

    // Subtle global rotation
    if (pointsRef.current) {
      pointsRef.current.rotation.y = t * 0.008;
    }
    if (filamentRef.current) {
      filamentRef.current.rotation.y = t * 0.008;
    }
  });

  const shaderMaterial = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: quantumVertexShader,
        fragmentShader: quantumFragmentShader,
        uniforms: uniforms.current,
        vertexColors: true,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    [],
  );

  const filamentMaterial = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: filamentVertexShader,
        fragmentShader: filamentFragmentShader,
        uniforms: filamentUniforms.current,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    [],
  );

  return (
    <lineSegments ref={filamentRef} material={filamentMaterial}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[filamentPositions, 3]} />
        <bufferAttribute attach="attributes-aProgress" args={[filamentProgress, 1]} />
        <bufferAttribute attach="attributes-aPairId" args={[filamentPairIds, 1]} />
      </bufferGeometry>
    </lineSegments>
  );
}

// ============================================================
// Probability fog — faint depth haze
// ============================================================
function ProbabilityFog() {
  const ref = useRef<THREE.Points>(null);
  const COUNT = 200;

  const { positions, sizes } = useMemo(() => {
    const pos = new Float32Array(COUNT * 3);
    const siz = new Float32Array(COUNT);
    for (let i = 0; i < COUNT; i++) {
      const r = Math.random() * 20;
      const theta = Math.random() * TAU_CONST;
      const phi = Math.acos(2 * Math.random() - 1);
      pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      pos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.5;
      pos[i * 3 + 2] = r * Math.cos(phi) * 0.3;
      siz[i] = 0.3 + Math.random() * 0.5;
    }
    return { positions: pos, sizes: siz };
  }, []);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.rotation.y = -clock.elapsedTime * 0.005;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.5}
        color="#0a1628"
        transparent
        opacity={0.15}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

// ============================================================
// Responsive camera
// ============================================================
function ResponsiveCamera() {
  const { camera, size } = useThree();
  const aspect = size.width / size.height;
  // Pull camera back on narrow screens so particles aren't clipped
  (camera as THREE.PerspectiveCamera).position.z = aspect < 1 ? 20 : 16;
  return null;
}

// ============================================================
// Export
// ============================================================
export function ParticleField() {
  return (
    <div className="absolute inset-0 z-0">
      <Canvas
        camera={{ position: [0, 0, 16], fov: 65 }}
        gl={{ alpha: true, antialias: true }}
        dpr={[1, 2]}
      >
        <ResponsiveCamera />
        <QuantumParticles />
      </Canvas>
    </div>
  );
}
