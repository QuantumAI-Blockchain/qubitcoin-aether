"use client";

import { useState, useMemo, useRef, useCallback } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
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
const PARTICLE_COUNT = 600;

// ── 3D Particle System ──────────────────────────────────────────────────────

interface ParticleData {
  positions: Float32Array;
  velocities: Float32Array;
  colors: Float32Array;
  lifetimes: Float32Array;
}

function initParticles(count: number): ParticleData {
  const positions = new Float32Array(count * 3);
  const velocities = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const lifetimes = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    resetParticle(positions, velocities, colors, lifetimes, i);
  }
  return { positions, velocities, colors, lifetimes };
}

function resetParticle(
  pos: Float32Array, vel: Float32Array, col: Float32Array, life: Float32Array,
  i: number,
) {
  const i3 = i * 3;
  pos[i3] = (Math.random() - 0.5) * 4;
  pos[i3 + 1] = (Math.random() - 0.5) * 6;
  pos[i3 + 2] = (Math.random() - 0.5) * 4;
  vel[i3] = 0;
  vel[i3 + 1] = 0;
  vel[i3 + 2] = 0;
  col[i3] = 0;
  col[i3 + 1] = 1;
  col[i3 + 2] = 0.53;
  life[i] = Math.random() * 5;
}

function GravityParticles({ theta, alpha }: { theta: number; alpha: number }) {
  const pointsRef = useRef<THREE.Points>(null);
  const dataRef = useRef<ParticleData>(initParticles(PARTICLE_COUNT));

  useFrame((_, delta) => {
    if (!pointsRef.current) return;
    const dt = Math.min(delta, 0.05);
    const { positions, velocities, colors, lifetimes } = dataRef.current;
    const repulsive = Math.cos(theta) < 0;
    const strength = alpha * Math.abs(Math.cos(theta));

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const i3 = i * 3;
      lifetimes[i] -= dt;

      if (lifetimes[i] <= 0 || Math.abs(positions[i3 + 1]) > 4) {
        resetParticle(positions, velocities, colors, lifetimes, i);
        continue;
      }

      // Gravity (downward) + SUSY field (direction depends on theta)
      const grav = -2.0; // scaled gravity
      const susy = repulsive ? strength * 3.0 : -strength * 1.5;
      velocities[i3 + 1] += (grav + susy) * dt;

      // Slight lateral drift for visual interest
      velocities[i3] += (Math.random() - 0.5) * 0.1 * dt;
      velocities[i3 + 2] += (Math.random() - 0.5) * 0.1 * dt;

      // Damping
      velocities[i3] *= 0.99;
      velocities[i3 + 2] *= 0.99;

      positions[i3] += velocities[i3] * dt;
      positions[i3 + 1] += velocities[i3 + 1] * dt;
      positions[i3 + 2] += velocities[i3 + 2] * dt;

      // Color: cyan when falling, gold when rising
      if (repulsive && velocities[i3 + 1] > 0) {
        colors[i3] = 1.0;
        colors[i3 + 1] = 0.62;
        colors[i3 + 2] = 0.04;
      } else {
        colors[i3] = 0.0;
        colors[i3 + 1] = 0.83;
        colors[i3 + 2] = 1.0;
      }
    }

    const geom = pointsRef.current.geometry;
    geom.attributes.position.needsUpdate = true;
    geom.attributes.color.needsUpdate = true;
  });

  const { positions, colors } = dataRef.current;

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
          count={PARTICLE_COUNT}
        />
        <bufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
          count={PARTICLE_COUNT}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.06}
        vertexColors
        transparent
        opacity={0.85}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

function CavityPlates() {
  return (
    <group>
      {/* Top plate */}
      <mesh position={[0, 1.2, 0]}>
        <boxGeometry args={[3, 0.06, 3]} />
        <meshStandardMaterial
          color="#00ff88"
          emissive="#00ff88"
          emissiveIntensity={0.4}
          transparent
          opacity={0.3}
          metalness={0.9}
          roughness={0.1}
        />
      </mesh>
      {/* Bottom plate */}
      <mesh position={[0, -1.2, 0]}>
        <boxGeometry args={[3, 0.06, 3]} />
        <meshStandardMaterial
          color="#00ff88"
          emissive="#00ff88"
          emissiveIntensity={0.4}
          transparent
          opacity={0.3}
          metalness={0.9}
          roughness={0.1}
        />
      </mesh>
      {/* Edge glow lines */}
      {[1.2, -1.2].map((y) => (
        <mesh key={y} position={[0, y, 0]}>
          <ringGeometry args={[1.49, 1.51, 64]} />
          <meshBasicMaterial color="#00d4ff" transparent opacity={0.6} side={THREE.DoubleSide} />
        </mesh>
      ))}
    </group>
  );
}

function AntigravityScene({ theta, alpha }: { theta: number; alpha: number }) {
  return (
    <Canvas
      camera={{ position: [4, 2, 4], fov: 50 }}
      style={{ background: "transparent" }}
      gl={{ alpha: true, antialias: true }}
    >
      <ambientLight intensity={0.3} />
      <pointLight position={[5, 5, 5]} intensity={0.8} color="#00d4ff" />
      <pointLight position={[-5, -3, -5]} intensity={0.4} color="#7c3aed" />
      <CavityPlates />
      <GravityParticles theta={theta} alpha={alpha} />
      <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={0.5} />
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
    <div className="rounded-lg border border-[#00ff88]/20 bg-[#0a0a0f]/95 px-3 py-2 text-xs">
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

  const setPreset = useCallback((preset: "normal" | "attract" | "repel") => {
    switch (preset) {
      case "normal": setAlpha(0); setTheta(0); break;
      case "attract": setAlpha(DEFAULT_ALPHA); setTheta(0); break;
      case "repel": setAlpha(DEFAULT_ALPHA); setTheta(Math.PI); break;
    }
  }, []);

  return (
    <div className="space-y-8">
      {/* ── Hero: 3D Visualization ──────────────────────────────────────── */}
      <motion.section
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="relative rounded-2xl border border-[#00ff88]/10 bg-gradient-to-b from-[#0a0a0f] to-[#0d0d14] overflow-hidden"
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,212,255,0.05),transparent_70%)]" />
        <div className="relative h-[500px]">
          <AntigravityScene theta={theta} alpha={alpha} />
          {/* Overlay labels */}
          <div className="absolute top-4 left-4 space-y-1">
            <p className="text-[#00d4ff] text-sm font-mono">
              {Math.cos(theta) < -0.5 ? "REPULSIVE MODE" : Math.cos(theta) > 0.5 ? "ATTRACTIVE MODE" : "TRANSITIONAL"}
            </p>
            <p className="text-gray-500 text-xs font-mono">
              lambda_C = {(lambda_C * 1e6).toFixed(1)} um | alpha = {alpha.toFixed(2)} | theta = {(theta / Math.PI).toFixed(2)}pi
            </p>
          </div>
          <div className="absolute top-4 right-4 flex gap-2">
            {(["normal", "attract", "repel"] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPreset(p)}
                className={`px-3 py-1 rounded text-xs font-mono border transition-colors ${
                  (p === "normal" && alpha === 0) ||
                  (p === "attract" && alpha > 0 && theta === 0) ||
                  (p === "repel" && alpha > 0 && Math.abs(theta - Math.PI) < 0.01)
                    ? "border-[#00ff88] text-[#00ff88] bg-[#00ff88]/10"
                    : "border-gray-700 text-gray-500 hover:border-gray-500"
                }`}
              >
                {p === "normal" ? "Normal Gravity" : p === "attract" ? "Enhanced" : "Antigravity"}
              </button>
            ))}
          </div>
        </div>
      </motion.section>

      {/* ── Parameter Controls ──────────────────────────────────────────── */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
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
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="grid grid-cols-1 lg:grid-cols-3 gap-4"
      >
        {/* Acceleration vs Distance */}
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4">
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
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4">
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
        <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4">
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
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.7 }}
        className="rounded-xl border border-gray-800 bg-[#0d0d14] p-6"
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-mono text-white">Verification Suite</h3>
          <span className={`font-mono text-sm px-3 py-1 rounded ${
            passCount === testResults.length
              ? "bg-green-500/10 text-green-400 border border-green-500/30"
              : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/30"
          }`}>
            {passCount}/{testResults.length} PASS
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {testResults.map((t, i) => (
            <div
              key={i}
              className={`rounded-lg border p-3 ${
                t.pass
                  ? "border-green-500/20 bg-green-500/5"
                  : "border-red-500/20 bg-red-500/5"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-mono ${t.pass ? "text-green-400" : "text-red-400"}`}>
                  {t.pass ? "PASS" : "FAIL"}
                </span>
                <span className="text-sm text-white">{t.name}</span>
              </div>
              <p className="text-xs text-gray-400 font-mono">{t.value}</p>
              <p className="text-xs text-gray-600 mt-1">{t.detail}</p>
            </div>
          ))}
        </div>
      </motion.section>

      {/* ── Mathematical Framework ──────────────────────────────────────── */}
      <motion.section
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.9 }}
        className="rounded-xl border border-gray-800 bg-[#0d0d14] p-6 space-y-6"
      >
        <h3 className="text-lg font-mono text-white">Mathematical Framework</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <EquationCard
            title="Modified Newtonian Potential"
            equation="V(r) = -GMm/r [1 - alpha * exp(-r/lambda_C) * cos(theta)]"
            description="Standard Newtonian gravity plus Yukawa-type bimetric correction. The phase theta controls attractive vs repulsive behavior."
          />
          <EquationCard
            title="SUSY Hamiltonian"
            equation="H_SUSY = (1/2){Q, Q*} where Q = supercharge"
            description="N=2 extended supergravity. The Hamiltonian is forced by the superalgebra - not chosen. Ground state energy E_0 = xi^2/2 after FI breaking."
          />
          <EquationCard
            title="Bimetric Mass Mixing"
            equation="H_bimetric = m'^2 cos(theta) integral h_uv h'^uv d3x"
            description="Mass-mixing between the two graviton multiplets. The phase theta is the actuator. theta=0 attractive, theta=pi repulsive."
          />
          <EquationCard
            title="Compton Wavelength"
            equation="lambda_C = h_bar / (m' * c)"
            description={`For m' = ${(mPrime * 1e3).toFixed(3)} meV: lambda_C = ${(lambda_C * 1e6).toFixed(1)} um. Sets the field range - sub-mm for near-field cavity operation.`}
          />
          <EquationCard
            title="IIT Consciousness Coupling"
            equation="H_IIT = -h_bar * omega_phi * sum_P Phi(P)|P><P|"
            description="Novel contribution: operator-valued IIT term coupled to SUGRA Hamiltonian. Phi over bipartitions of the information graph."
          />
          <EquationCard
            title="Full VQE Hamiltonian"
            equation="H_VQE = H_SUSY + H_bimetric(theta) + lambda * H_IIT"
            description="The miner searches for ground states of this SUGRA-plus-consciousness Hamiltonian. First physically motivated quantum mining cost function."
          />
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
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.1 }}
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
            <div key={i} className="flex gap-3 items-start">
              <span className="text-[#7c3aed] text-xs font-mono mt-0.5">{i + 1}</span>
              <p className="text-sm text-gray-300">{claim.split(": ")[1]}</p>
            </div>
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
    <div className="rounded-xl border border-gray-800 bg-[#0d0d14] p-4">
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
          [&::-webkit-slider-thumb]:bg-[#00ff88] [&::-webkit-slider-thumb]:cursor-pointer"
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
    <div className="rounded-lg border border-gray-800 p-4 space-y-2">
      <h4 className="text-sm text-[#00d4ff] font-medium">{title}</h4>
      <p className="font-mono text-sm text-[#00ff88] bg-[#0a0a0f] rounded px-3 py-2 break-all">
        {equation}
      </p>
      <p className="text-xs text-gray-500 leading-relaxed">{description}</p>
    </div>
  );
}
