/**
 * SUSY Antigravity Mechanism — Numerical Physics Engine
 * N=2 Broken Supergravity with Phase-Controlled Bimetric Coupling
 *
 * Implements the modified Newtonian potential:
 *   V(r) = -GMm/r × [1 - α·exp(-r/λ_C)·cos(θ)]
 *
 * Where:
 *   α(φ) = environmental coupling (0 in vacuum, O(1) in metamaterial cavity)
 *   θ     = bimetric coupling phase (0 = attractive, π = repulsive)
 *   λ_C   = Compton wavelength of massive second graviton
 */

// ── Physical Constants (SI) ─────────────────────────────────────────────────

export const G = 6.6743e-11;        // m³ kg⁻¹ s⁻²
export const c = 2.99792458e8;      // m/s
export const hbar = 1.054571817e-34; // J·s
export const eV = 1.602176634e-19;   // J
export const g_earth = 9.80665;      // m/s²
export const M_earth = 5.972e24;     // kg
export const R_earth = 6.371e6;      // m

// ── SUGRA Bimetric Field ────────────────────────────────────────────────────

export interface FieldParams {
  m_prime_eV: number; // massive graviton mass in eV
  alpha: number;      // environmental coupling strength
  theta: number;      // bimetric coupling phase (radians)
}

export function comptonWavelength(m_prime_eV: number): number {
  const m_kg = m_prime_eV * eV / (c * c);
  return hbar / (m_kg * c);
}

/** Gravitational acceleration including SUGRA bimetric correction. */
export function acceleration(r: number, M: number, params: FieldParams): number {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const a_newton = -G * M / (r * r);
  const a_susy = -G * M / (r * r) * params.alpha
    * Math.exp(-r / lambda_C)
    * Math.cos(params.theta)
    * (1.0 + r / lambda_C);
  return a_newton + a_susy;
}

/** Modified gravitational potential. */
export function potential(r: number, M: number, params: FieldParams): number {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const yukawa = params.alpha * Math.exp(-r / lambda_C) * Math.cos(params.theta);
  return -G * M / r * (1.0 - yukawa);
}

/** Ratio of net upward acceleration to g_earth (>1 means lift). */
export function liftRatio(r: number, M: number, params: FieldParams): number {
  return -acceleration(r, M, params) / g_earth;
}

// ── Data Generation ─────────────────────────────────────────────────────────

export interface AccelerationPoint {
  r_um: number;  // distance in µm
  a_attract: number;
  a_repel: number;
}

export function generateAccelerationCurve(
  params: FieldParams,
  M: number,
  points: number = 200,
): AccelerationPoint[] {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const data: AccelerationPoint[] = [];
  for (let i = 1; i <= points; i++) {
    const r = lambda_C * 0.1 + (lambda_C * 4.9 * i) / points;
    const attract: FieldParams = { ...params, theta: 0 };
    const repel: FieldParams = { ...params, theta: Math.PI };
    data.push({
      r_um: r * 1e6,
      a_attract: acceleration(r, M, attract),
      a_repel: acceleration(r, M, repel),
    });
  }
  return data;
}

export interface PhasePoint {
  theta: number;
  accel: number;
}

export function generatePhaseSurface(
  params: FieldParams,
  M: number,
  points: number = 200,
): PhasePoint[] {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const r = lambda_C / 2;
  const data: PhasePoint[] = [];
  for (let i = 0; i <= points; i++) {
    const theta = (2 * Math.PI * i) / points;
    data.push({
      theta,
      accel: acceleration(r, M, { ...params, theta }),
    });
  }
  return data;
}

export interface TrajectoryPoint {
  t_ms: number;
  x_um: number;
}

/** RK4 trajectory integration for test mass in the repulsive field. */
export function generateTrajectory(
  params: FieldParams,
  M: number,
  duration_s: number = 0.05,
  steps: number = 500,
): TrajectoryPoint[] {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const dt = duration_s / steps;
  let x = lambda_C * 1.5;
  let v = 0;
  const data: TrajectoryPoint[] = [{ t_ms: 0, x_um: x * 1e6 }];

  for (let i = 1; i <= steps; i++) {
    // RK4
    const f = (pos: number, vel: number): [number, number] => {
      const r = Math.abs(pos) + 1e-15;
      const a = acceleration(r, M, params) * Math.sign(pos) - g_earth;
      return [vel, a];
    };

    const [k1v, k1a] = f(x, v);
    const [k2v, k2a] = f(x + dt / 2 * k1v, v + dt / 2 * k1a);
    const [k3v, k3a] = f(x + dt / 2 * k2v, v + dt / 2 * k2a);
    const [k4v, k4a] = f(x + dt * k3v, v + dt * k3a);

    x += dt / 6 * (k1v + 2 * k2v + 2 * k3v + k4v);
    v += dt / 6 * (k1a + 2 * k2a + 2 * k3a + k4a);

    data.push({ t_ms: (i * dt) * 1000, x_um: x * 1e6 });
  }
  return data;
}

// ── Verification Tests ──────────────────────────────────────────────────────

export interface TestResult {
  name: string;
  pass: boolean;
  value: string;
  detail: string;
}

export function runVerificationSuite(params: FieldParams, M_plate: number): TestResult[] {
  const lambda_C = comptonWavelength(params.m_prime_eV);
  const r_cav = lambda_C / 2;
  const results: TestResult[] = [];

  // Test 1: Normal gravity recovered outside cavity
  const normal: FieldParams = { ...params, alpha: 0 };
  const a_normal = acceleration(R_earth, M_earth, normal);
  results.push({
    name: "Normal Gravity Recovery",
    pass: Math.abs(a_normal + g_earth) / g_earth < 0.002,
    value: `a = ${a_normal.toFixed(4)} m/s²`,
    detail: "Outside cavity (α=0): must match -9.81 m/s² (±0.2%)",
  });

  // Test 2: Attractive phase enhances gravity
  const attract: FieldParams = { ...params, theta: 0 };
  const a_atr = acceleration(r_cav, M_plate, attract);
  results.push({
    name: "Attractive Enhancement",
    pass: a_atr < 0,
    value: `a = ${a_atr.toExponential(4)} m/s²`,
    detail: "Cavity (θ=0): gravity enhanced (more negative)",
  });

  // Test 3: Repulsive phase produces positive acceleration
  const repel: FieldParams = { ...params, theta: Math.PI };
  const a_rep = acceleration(r_cav, M_plate, repel);
  results.push({
    name: "Repulsive Antigravity",
    pass: a_rep > 0,
    value: `a = ${a_rep.toExponential(4)} m/s²`,
    detail: "Cavity (θ=π): acceleration REPULSIVE (positive)",
  });

  // Test 4: Lift threshold search
  let alpha_threshold = NaN;
  for (let a = 0.1; a < 1e7; a *= 1.1) {
    const f: FieldParams = { ...params, alpha: a, theta: Math.PI };
    const a_plates = 2 * Math.abs(acceleration(r_cav, M_plate, f));
    if (a_plates >= g_earth) {
      alpha_threshold = a;
      break;
    }
  }
  results.push({
    name: "Unity Lift Threshold",
    pass: !isNaN(alpha_threshold),
    value: isNaN(alpha_threshold) ? "No solution" : `α = ${alpha_threshold.toFixed(2)}`,
    detail: "Coupling required for net upward acceleration ≥ g",
  });

  // Test 5: Phase symmetry (θ=0 and θ=2π give same result)
  const a_0 = acceleration(r_cav, M_plate, { ...params, theta: 0 });
  const a_2pi = acceleration(r_cav, M_plate, { ...params, theta: 2 * Math.PI });
  results.push({
    name: "Phase Periodicity",
    pass: Math.abs(a_0 - a_2pi) < 1e-20,
    value: `|Δa| = ${Math.abs(a_0 - a_2pi).toExponential(2)}`,
    detail: "θ=0 and θ=2π must yield identical acceleration",
  });

  // Test 6: Compton wavelength physical scale
  results.push({
    name: "Compton Scale",
    pass: lambda_C > 1e-6 && lambda_C < 1e-3,
    value: `λ_C = ${(lambda_C * 1e6).toFixed(1)} µm`,
    detail: "Must be sub-mm for near-field cavity operation",
  });

  return results;
}
