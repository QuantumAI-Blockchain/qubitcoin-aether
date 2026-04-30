"use client";

import { useState, useCallback, useMemo, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

// ═══════════════════════════════════════════════════════════════════════
// Types
// ═══════════════════════════════════════════════════════════════════════

interface Opening {
  id: string;
  type: "door" | "window" | "archway" | "custom";
  width: number;
  height: number;
  qty: number;
}

interface Room {
  id: string;
  name: string;
  length: number;
  width: number;
  height: number;
  ceilingType: "flat" | "raked" | "bulkhead" | "none";
  rakedMaxHeight: number;
  openings: Opening[];
  wallFinish: keyof typeof WALL_FINISHES;
  ceilingFinish: keyof typeof CEILING_FINISHES;
  corniceType: keyof typeof CORNICE_RATES;
  notes: string;
}

interface MaterialItem {
  name: string;
  qty: number;
  unit: string;
  unitCost: number;
  total: number;
}

// ═══════════════════════════════════════════════════════════════════════
// Rate Tables (AUD, 2026 market rates — researched)
// ═══════════════════════════════════════════════════════════════════════

const WALL_FINISHES = {
  plasterboard_supply_fix: { label: "Plasterboard Supply & Fix (10mm)", rate: 38, unit: "/m²" },
  plasterboard_13mm: { label: "Plasterboard Supply & Fix (13mm)", rate: 42, unit: "/m²" },
  plasterboard_fire: { label: "Fire-Rated Board (16mm FRL)", rate: 58, unit: "/m²" },
  plasterboard_moisture: { label: "Moisture-Resistant Board", rate: 48, unit: "/m²" },
  plasterboard_sound: { label: "SoundChek Acoustic Board", rate: 55, unit: "/m²" },
  set_coat: { label: "Set / Flush Coat (L4)", rate: 22, unit: "/m²" },
  skim_coat: { label: "Skim Coat (L5)", rate: 28, unit: "/m²" },
  sand_finish: { label: "Sand Finish Render", rate: 45, unit: "/m²" },
  patch_repair: { label: "Patch & Repair", rate: 75, unit: "/m²" },
  texture_coat: { label: "Texture Coat (Knocked Down)", rate: 35, unit: "/m²" },
  venetian: { label: "Venetian Plaster", rate: 120, unit: "/m²" },
  none: { label: "None (Existing)", rate: 0, unit: "/m²" },
} as const;

const CEILING_FINISHES = {
  plasterboard_supply_fix: { label: "Plasterboard Supply & Fix (10mm)", rate: 45, unit: "/m²" },
  plasterboard_13mm: { label: "Plasterboard Supply & Fix (13mm)", rate: 50, unit: "/m²" },
  plasterboard_fire: { label: "Fire-Rated Ceiling (16mm)", rate: 65, unit: "/m²" },
  set_coat: { label: "Set / Flush Coat (L4)", rate: 24, unit: "/m²" },
  skim_coat: { label: "Skim Coat (L5)", rate: 30, unit: "/m²" },
  suspended_grid: { label: "Suspended Grid Ceiling", rate: 85, unit: "/m²" },
  bulkhead: { label: "Bulkhead Formation", rate: 95, unit: "/m²" },
  none: { label: "None", rate: 0, unit: "/m²" },
} as const;

const CORNICE_RATES = {
  cove_55: { label: "Cove 55mm", rate: 9, unit: "/lm" },
  cove_75: { label: "Cove 75mm", rate: 11, unit: "/lm" },
  cove_90: { label: "Cove 90mm", rate: 13, unit: "/lm" },
  victorian: { label: "Victorian Ornamental", rate: 24, unit: "/lm" },
  art_deco: { label: "Art Deco Profile", rate: 28, unit: "/lm" },
  square_set: { label: "Square Set (Shadow Line)", rate: 18, unit: "/lm" },
  custom_profile: { label: "Custom Profile", rate: 35, unit: "/lm" },
  none: { label: "None", rate: 0, unit: "/lm" },
} as const;

const DEFAULT_OPENINGS: Record<string, { width: number; height: number }> = {
  door: { width: 0.87, height: 2.04 },
  window: { width: 1.2, height: 1.2 },
  archway: { width: 1.0, height: 2.4 },
  custom: { width: 1.0, height: 1.0 },
};

const MATERIAL_COSTS = {
  plasterboard_10mm: { name: "Plasterboard 10mm (2400×1200)", cost: 18.50, coversM2: 2.88 },
  plasterboard_13mm: { name: "Plasterboard 13mm (2400×1200)", cost: 22.00, coversM2: 2.88 },
  plasterboard_fire: { name: "Fire-Rated 16mm (2400×1200)", cost: 38.00, coversM2: 2.88 },
  plasterboard_moisture: { name: "Moisture Board (2400×1200)", cost: 32.00, coversM2: 2.88 },
  compound_20kg: { name: "Base Coat Compound 20kg", cost: 28.50, coversM2: 12 },
  compound_top: { name: "Top Coat Compound 15kg", cost: 32.00, coversM2: 15 },
  cornice_cove_55: { name: "Cove Cornice 55mm (4.2m)", cost: 8.50, coversLm: 4.2 },
  cornice_cove_75: { name: "Cove Cornice 75mm (4.2m)", cost: 12.00, coversLm: 4.2 },
  tape: { name: "Paper Tape 75m Roll", cost: 8.50, coversM2: 30 },
  screws: { name: "Screws 32mm (1000pk)", cost: 22.00, coversM2: 45 },
  adhesive: { name: "Cornice Adhesive 5kg", cost: 14.50, coversLm: 25 },
  angle_bead: { name: "Angle Bead 3.0m", cost: 4.20, coversLm: 3.0 },
};

const WASTE_FACTOR = 1.10; // 10% waste
const LABOUR_RATE_HR = 65; // $/hr standard plasterer
const LABOUR_RATE_APPRENTICE = 38;

// ═══════════════════════════════════════════════════════════════════════
// Utility Functions
// ═══════════════════════════════════════════════════════════════════════

function genId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function createRoom(index: number): Room {
  return {
    id: genId(),
    name: `Room ${index + 1}`,
    length: 0,
    width: 0,
    height: 2.7,
    ceilingType: "flat",
    rakedMaxHeight: 3.6,
    openings: [],
    wallFinish: "plasterboard_supply_fix",
    ceilingFinish: "plasterboard_supply_fix",
    corniceType: "cove_75",
    notes: "",
  };
}

function calcRoomAreas(room: Room) {
  const perimeter = 2 * (room.length + room.width);
  const grossWallArea = perimeter * room.height;
  const openingsArea = room.openings.reduce(
    (sum, o) => sum + o.width * o.height * o.qty,
    0
  );
  const netWallArea = Math.max(0, grossWallArea - openingsArea);
  let ceilingArea = room.length * room.width;
  if (room.ceilingType === "raked") {
    const avgH = (room.height + room.rakedMaxHeight) / 2;
    ceilingArea = room.length * room.width * (avgH / room.height);
  }
  if (room.ceilingType === "none") ceilingArea = 0;
  const corniceLength = room.ceilingType !== "none" ? perimeter : 0;
  const floorArea = room.length * room.width;
  return { perimeter, grossWallArea, openingsArea, netWallArea, ceilingArea, corniceLength, floorArea };
}

// ═══════════════════════════════════════════════════════════════════════
// Components
// ═══════════════════════════════════════════════════════════════════════

function NumberInput({
  label,
  value,
  onChange,
  unit = "m",
  min = 0,
  step = 0.01,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  min?: number;
  step?: number;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-zinc-400 uppercase tracking-wider">{label}</label>
      <div className="relative">
        <input
          type="number"
          value={value || ""}
          onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
          min={min}
          step={step}
          className="w-full bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/30 focus:outline-none placeholder-zinc-600 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
          placeholder="0"
        />
        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-zinc-500">{unit}</span>
      </div>
    </div>
  );
}

function SelectInput<T extends string>({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string; detail?: string }[];
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs text-zinc-400 uppercase tracking-wider">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        className="w-full bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-amber-500/60 focus:ring-1 focus:ring-amber-500/30 focus:outline-none cursor-pointer"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}{o.detail ? ` — ${o.detail}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}

function Stat({ label, value, unit, accent = false }: { label: string; value: string; unit?: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${accent ? "border-amber-500/30 bg-amber-500/5" : "border-zinc-700/40 bg-zinc-900/40"}`}>
      <div className="text-xs text-zinc-400 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-xl font-semibold font-mono ${accent ? "text-amber-400" : "text-white"}`}>
        {value}
        {unit && <span className="text-xs text-zinc-500 ml-1">{unit}</span>}
      </div>
    </div>
  );
}

function RoomCard({
  room,
  index,
  onUpdate,
  onRemove,
  onDuplicate,
}: {
  room: Room;
  index: number;
  onUpdate: (room: Room) => void;
  onRemove: () => void;
  onDuplicate: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const areas = calcRoomAreas(room);

  const wallFinishOptions = Object.entries(WALL_FINISHES).map(([k, v]) => ({
    value: k,
    label: v.label,
    detail: v.rate > 0 ? `$${v.rate}${v.unit}` : undefined,
  }));
  const ceilingFinishOptions = Object.entries(CEILING_FINISHES).map(([k, v]) => ({
    value: k,
    label: v.label,
    detail: v.rate > 0 ? `$${v.rate}${v.unit}` : undefined,
  }));
  const corniceOptions = Object.entries(CORNICE_RATES).map(([k, v]) => ({
    value: k,
    label: v.label,
    detail: v.rate > 0 ? `$${v.rate}${v.unit}` : undefined,
  }));

  const addOpening = (type: Opening["type"]) => {
    const defaults = DEFAULT_OPENINGS[type];
    onUpdate({
      ...room,
      openings: [...room.openings, { id: genId(), type, ...defaults, qty: 1 }],
    });
  };

  const updateOpening = (id: string, patch: Partial<Opening>) => {
    onUpdate({
      ...room,
      openings: room.openings.map((o) => (o.id === id ? { ...o, ...patch } : o)),
    });
  };

  const removeOpening = (id: string) => {
    onUpdate({ ...room, openings: room.openings.filter((o) => o.id !== id) });
  };

  const wallCost = areas.netWallArea * WALL_FINISHES[room.wallFinish].rate;
  const ceilCost = areas.ceilingArea * CEILING_FINISHES[room.ceilingFinish].rate;
  const corniceCost = areas.corniceLength * CORNICE_RATES[room.corniceType].rate;
  const roomTotal = wallCost + ceilCost + corniceCost;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="border border-zinc-700/40 rounded-2xl bg-zinc-900/30 backdrop-blur-sm overflow-hidden"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-3 bg-zinc-800/40 cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 text-sm font-bold">
            {index + 1}
          </span>
          <input
            value={room.name}
            onChange={(e) => onUpdate({ ...room, name: e.target.value })}
            onClick={(e) => e.stopPropagation()}
            className="bg-transparent text-white font-semibold text-lg focus:outline-none border-b border-transparent focus:border-amber-500/40 px-1"
          />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-zinc-400 font-mono">
            {areas.floorArea.toFixed(1)}m² floor &middot; ${roomTotal.toFixed(0)}
          </span>
          <button onClick={(e) => { e.stopPropagation(); onDuplicate(); }}
            className="text-xs text-zinc-400 hover:text-amber-400 px-2 py-1 rounded border border-zinc-700/40 hover:border-amber-500/30 transition-colors"
          >
            Duplicate
          </button>
          <button onClick={(e) => { e.stopPropagation(); onRemove(); }}
            className="text-xs text-red-400/60 hover:text-red-400 px-2 py-1 rounded border border-zinc-700/40 hover:border-red-500/30 transition-colors"
          >
            Remove
          </button>
          <span className={`text-zinc-500 transition-transform ${expanded ? "rotate-180" : ""}`}>&#9660;</span>
        </div>
      </div>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: "auto" }}
            exit={{ height: 0 }}
            className="overflow-hidden"
          >
            <div className="px-5 py-4 space-y-4">
              {/* Dimensions */}
              <div className="grid grid-cols-4 gap-3">
                <NumberInput label="Length" value={room.length} onChange={(v) => onUpdate({ ...room, length: v })} />
                <NumberInput label="Width" value={room.width} onChange={(v) => onUpdate({ ...room, width: v })} />
                <NumberInput label="Ceiling Height" value={room.height} onChange={(v) => onUpdate({ ...room, height: v })} />
                <SelectInput
                  label="Ceiling Type"
                  value={room.ceilingType}
                  onChange={(v) => onUpdate({ ...room, ceilingType: v })}
                  options={[
                    { value: "flat", label: "Flat" },
                    { value: "raked", label: "Raked / Cathedral" },
                    { value: "bulkhead", label: "Bulkhead" },
                    { value: "none", label: "No Ceiling Work" },
                  ]}
                />
              </div>

              {room.ceilingType === "raked" && (
                <div className="grid grid-cols-4 gap-3">
                  <NumberInput label="Max Rake Height" value={room.rakedMaxHeight} onChange={(v) => onUpdate({ ...room, rakedMaxHeight: v })} />
                </div>
              )}

              {/* Finishes */}
              <div className="grid grid-cols-3 gap-3">
                <SelectInput label="Wall Finish" value={room.wallFinish} onChange={(v) => onUpdate({ ...room, wallFinish: v as keyof typeof WALL_FINISHES })} options={wallFinishOptions} />
                <SelectInput label="Ceiling Finish" value={room.ceilingFinish} onChange={(v) => onUpdate({ ...room, ceilingFinish: v as keyof typeof CEILING_FINISHES })} options={ceilingFinishOptions} />
                <SelectInput label="Cornice" value={room.corniceType} onChange={(v) => onUpdate({ ...room, corniceType: v as keyof typeof CORNICE_RATES })} options={corniceOptions} />
              </div>

              {/* Openings */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-400 uppercase tracking-wider">Deductions (Openings)</span>
                  <div className="flex gap-1">
                    {(["door", "window", "archway", "custom"] as const).map((t) => (
                      <button
                        key={t}
                        onClick={() => addOpening(t)}
                        className="text-xs px-2 py-1 rounded bg-zinc-800 border border-zinc-700/40 text-zinc-300 hover:border-amber-500/30 hover:text-amber-400 transition-colors capitalize"
                      >
                        + {t}
                      </button>
                    ))}
                  </div>
                </div>
                {room.openings.length > 0 && (
                  <div className="space-y-1">
                    {room.openings.map((o) => (
                      <div key={o.id} className="flex items-center gap-2 text-sm">
                        <span className="text-zinc-400 capitalize w-16">{o.type}</span>
                        <NumberInput label="" value={o.width} onChange={(v) => updateOpening(o.id, { width: v })} unit="W" />
                        <span className="text-zinc-600">×</span>
                        <NumberInput label="" value={o.height} onChange={(v) => updateOpening(o.id, { height: v })} unit="H" />
                        <span className="text-zinc-600">×</span>
                        <NumberInput label="" value={o.qty} onChange={(v) => updateOpening(o.id, { qty: Math.max(1, Math.round(v)) })} unit="qty" min={1} step={1} />
                        <span className="text-zinc-500 font-mono text-xs w-16 text-right">
                          {(o.width * o.height * o.qty).toFixed(1)}m²
                        </span>
                        <button onClick={() => removeOpening(o.id)} className="text-red-400/50 hover:text-red-400 text-xs">✕</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Room Stats */}
              <div className="grid grid-cols-5 gap-2 pt-2 border-t border-zinc-800">
                <Stat label="Gross Wall" value={areas.grossWallArea.toFixed(1)} unit="m²" />
                <Stat label="Deductions" value={areas.openingsArea.toFixed(1)} unit="m²" />
                <Stat label="Net Wall" value={areas.netWallArea.toFixed(1)} unit="m²" />
                <Stat label="Ceiling" value={areas.ceilingArea.toFixed(1)} unit="m²" />
                <Stat label="Room Total" value={`$${roomTotal.toFixed(0)}`} accent />
              </div>

              {/* Notes */}
              <textarea
                value={room.notes}
                onChange={(e) => onUpdate({ ...room, notes: e.target.value })}
                placeholder="Notes (access issues, heights, prep work...)"
                rows={2}
                className="w-full bg-zinc-900/60 border border-zinc-700/30 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:border-amber-500/40 focus:outline-none resize-none placeholder-zinc-600"
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// Main Dashboard
// ═══════════════════════════════════════════════════════════════════════

export default function PlasterDashboard() {
  const [rooms, setRooms] = useState<Room[]>([createRoom(0)]);
  const [marginPercent, setMarginPercent] = useState(20);
  const [labourMultiplier, setLabourMultiplier] = useState(1.0);
  const [showMaterials, setShowMaterials] = useState(false);
  const [clientName, setClientName] = useState("");
  const [jobAddress, setJobAddress] = useState("");
  const [quoteRef, setQuoteRef] = useState(`PL-${Date.now().toString(36).toUpperCase().slice(-6)}`);
  const printRef = useRef<HTMLDivElement>(null);

  const addRoom = () => setRooms([...rooms, createRoom(rooms.length)]);
  const removeRoom = (id: string) => setRooms(rooms.filter((r) => r.id !== id));
  const updateRoom = (id: string, room: Room) => setRooms(rooms.map((r) => (r.id === id ? room : r)));
  const duplicateRoom = (room: Room) => {
    const clone = { ...room, id: genId(), name: `${room.name} (copy)`, openings: room.openings.map(o => ({ ...o, id: genId() })) };
    setRooms([...rooms, clone]);
  };

  // ── Totals ──────────────────────────────────────────────────────────
  const totals = useMemo(() => {
    let totalWallArea = 0;
    let totalCeilingArea = 0;
    let totalCorniceLength = 0;
    let totalWallCost = 0;
    let totalCeilingCost = 0;
    let totalCorniceCost = 0;
    let totalFloorArea = 0;

    for (const room of rooms) {
      const a = calcRoomAreas(room);
      totalWallArea += a.netWallArea;
      totalCeilingArea += a.ceilingArea;
      totalCorniceLength += a.corniceLength;
      totalFloorArea += a.floorArea;
      totalWallCost += a.netWallArea * WALL_FINISHES[room.wallFinish].rate;
      totalCeilingCost += a.ceilingArea * CEILING_FINISHES[room.ceilingFinish].rate;
      totalCorniceCost += a.corniceLength * CORNICE_RATES[room.corniceType].rate;
    }

    const subtotal = totalWallCost + totalCeilingCost + totalCorniceCost;
    const labourEstimate = ((totalWallArea + totalCeilingArea) * 0.35 + totalCorniceLength * 0.15) * labourMultiplier;
    const labourCost = labourEstimate * LABOUR_RATE_HR;
    const materialEstimate = subtotal * 0.4;
    const margin = subtotal * (marginPercent / 100);
    const gstRate = 0.10;
    const exGst = subtotal + margin;
    const gst = exGst * gstRate;
    const total = exGst + gst;
    const perM2 = (totalWallArea + totalCeilingArea) > 0
      ? exGst / (totalWallArea + totalCeilingArea)
      : 0;

    return {
      totalWallArea, totalCeilingArea, totalCorniceLength, totalFloorArea,
      totalWallCost, totalCeilingCost, totalCorniceCost,
      subtotal, labourEstimate, labourCost, materialEstimate,
      margin, marginPercent, exGst, gst, total, perM2,
      roomCount: rooms.length,
    };
  }, [rooms, marginPercent, labourMultiplier]);

  // ── Materials Takeoff ──────────────────────────────────────────────
  const materials = useMemo((): MaterialItem[] => {
    const items: MaterialItem[] = [];
    let boardArea = 0;
    let compoundArea = 0;
    let corniceLm = 0;

    for (const room of rooms) {
      const a = calcRoomAreas(room);
      if (room.wallFinish.startsWith("plasterboard")) boardArea += a.netWallArea;
      if (room.ceilingFinish.startsWith("plasterboard")) boardArea += a.ceilingArea;
      if (room.wallFinish.includes("coat") || room.wallFinish.includes("skim")) compoundArea += a.netWallArea;
      if (room.ceilingFinish.includes("coat") || room.ceilingFinish.includes("skim")) compoundArea += a.ceilingArea;
      // All board needs compound for joints
      if (room.wallFinish.startsWith("plasterboard")) compoundArea += a.netWallArea * 0.3;
      if (room.ceilingFinish.startsWith("plasterboard")) compoundArea += a.ceilingArea * 0.3;
      if (room.corniceType !== "none") corniceLm += a.corniceLength;
    }

    boardArea *= WASTE_FACTOR;
    compoundArea *= WASTE_FACTOR;
    corniceLm *= WASTE_FACTOR;

    if (boardArea > 0) {
      const sheets = Math.ceil(boardArea / MATERIAL_COSTS.plasterboard_10mm.coversM2);
      items.push({ name: MATERIAL_COSTS.plasterboard_10mm.name, qty: sheets, unit: "sheets", unitCost: MATERIAL_COSTS.plasterboard_10mm.cost, total: sheets * MATERIAL_COSTS.plasterboard_10mm.cost });
      const screwPacks = Math.ceil(boardArea / MATERIAL_COSTS.screws.coversM2);
      items.push({ name: MATERIAL_COSTS.screws.name, qty: screwPacks, unit: "packs", unitCost: MATERIAL_COSTS.screws.cost, total: screwPacks * MATERIAL_COSTS.screws.cost });
    }
    if (compoundArea > 0) {
      const baseBags = Math.ceil(compoundArea / MATERIAL_COSTS.compound_20kg.coversM2);
      items.push({ name: MATERIAL_COSTS.compound_20kg.name, qty: baseBags, unit: "bags", unitCost: MATERIAL_COSTS.compound_20kg.cost, total: baseBags * MATERIAL_COSTS.compound_20kg.cost });
      const topBags = Math.ceil(compoundArea / MATERIAL_COSTS.compound_top.coversM2);
      items.push({ name: MATERIAL_COSTS.compound_top.name, qty: topBags, unit: "bags", unitCost: MATERIAL_COSTS.compound_top.cost, total: topBags * MATERIAL_COSTS.compound_top.cost });
      const tapeRolls = Math.ceil(boardArea / MATERIAL_COSTS.tape.coversM2);
      if (tapeRolls > 0) items.push({ name: MATERIAL_COSTS.tape.name, qty: tapeRolls, unit: "rolls", unitCost: MATERIAL_COSTS.tape.cost, total: tapeRolls * MATERIAL_COSTS.tape.cost });
    }
    if (corniceLm > 0) {
      const sticks = Math.ceil(corniceLm / MATERIAL_COSTS.cornice_cove_75.coversLm);
      items.push({ name: MATERIAL_COSTS.cornice_cove_75.name, qty: sticks, unit: "sticks", unitCost: MATERIAL_COSTS.cornice_cove_75.cost, total: sticks * MATERIAL_COSTS.cornice_cove_75.cost });
      const adhesiveBags = Math.ceil(corniceLm / MATERIAL_COSTS.adhesive.coversLm);
      items.push({ name: MATERIAL_COSTS.adhesive.name, qty: adhesiveBags, unit: "bags", unitCost: MATERIAL_COSTS.adhesive.cost, total: adhesiveBags * MATERIAL_COSTS.adhesive.cost });
    }

    return items;
  }, [rooms]);

  const materialTotal = materials.reduce((s, m) => s + m.total, 0);

  // ── Cost Breakdown Chart (CSS bars) ────────────────────────────────
  const maxCost = Math.max(totals.totalWallCost, totals.totalCeilingCost, totals.totalCorniceCost, 1);
  const costBars = [
    { label: "Walls", value: totals.totalWallCost, color: "bg-blue-500" },
    { label: "Ceilings", value: totals.totalCeilingCost, color: "bg-emerald-500" },
    { label: "Cornice", value: totals.totalCorniceCost, color: "bg-amber-500" },
    { label: "Margin", value: totals.margin, color: "bg-purple-500" },
  ];

  const handlePrint = useCallback(() => {
    window.print();
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white" ref={printRef}>
      {/* Header */}
      <div className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-xl sticky top-0 z-50 print:static">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center font-bold text-black text-lg">
              P
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Plaster Estimator</h1>
              <p className="text-xs text-zinc-500">Professional Plastering Cost Analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-3 print:hidden">
            <button
              onClick={() => setShowMaterials(!showMaterials)}
              className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                showMaterials
                  ? "bg-amber-500/10 border-amber-500/30 text-amber-400"
                  : "bg-zinc-800 border-zinc-700/40 text-zinc-300 hover:border-amber-500/30"
              }`}
            >
              Materials Takeoff
            </button>
            <button
              onClick={handlePrint}
              className="px-4 py-2 rounded-lg text-sm font-medium bg-amber-500 text-black hover:bg-amber-400 transition-colors"
            >
              Print Quote
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">
        {/* Job Info */}
        <div className="grid grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Client</label>
            <input
              value={clientName}
              onChange={(e) => setClientName(e.target.value)}
              placeholder="Client name"
              className="bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-amber-500/60 focus:outline-none placeholder-zinc-600"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Job Address</label>
            <input
              value={jobAddress}
              onChange={(e) => setJobAddress(e.target.value)}
              placeholder="Site address"
              className="bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-white focus:border-amber-500/60 focus:outline-none placeholder-zinc-600"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-zinc-400 uppercase tracking-wider">Quote Ref</label>
            <input
              value={quoteRef}
              onChange={(e) => setQuoteRef(e.target.value)}
              className="bg-zinc-900/80 border border-zinc-700/50 rounded-lg px-3 py-2 text-sm text-white font-mono focus:border-amber-500/60 focus:outline-none"
            />
          </div>
        </div>

        {/* Summary Strip */}
        <div className="grid grid-cols-7 gap-3">
          <Stat label="Rooms" value={totals.roomCount.toString()} />
          <Stat label="Total Wall" value={totals.totalWallArea.toFixed(1)} unit="m²" />
          <Stat label="Total Ceiling" value={totals.totalCeilingArea.toFixed(1)} unit="m²" />
          <Stat label="Cornice" value={totals.totalCorniceLength.toFixed(1)} unit="lm" />
          <Stat label="Avg $/m²" value={`$${totals.perM2.toFixed(0)}`} />
          <Stat label="Subtotal" value={`$${totals.subtotal.toFixed(0)}`} />
          <Stat label="Total (inc GST)" value={`$${totals.total.toFixed(0)}`} accent />
        </div>

        {/* Controls Strip */}
        <div className="flex items-end gap-4 print:hidden">
          <NumberInput label="Margin %" value={marginPercent} onChange={setMarginPercent} unit="%" min={0} step={1} />
          <NumberInput label="Labour Multiplier" value={labourMultiplier} onChange={setLabourMultiplier} unit="×" min={0.5} step={0.1} />
          <div className="flex-1" />
          <button
            onClick={addRoom}
            className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 text-black font-semibold hover:from-amber-400 hover:to-orange-400 transition-all text-sm shadow-lg shadow-amber-500/20"
          >
            + Add Room
          </button>
        </div>

        {/* Rooms */}
        <div className="space-y-4">
          <AnimatePresence>
            {rooms.map((room, i) => (
              <RoomCard
                key={room.id}
                room={room}
                index={i}
                onUpdate={(r) => updateRoom(room.id, r)}
                onRemove={() => removeRoom(room.id)}
                onDuplicate={() => duplicateRoom(room)}
              />
            ))}
          </AnimatePresence>
        </div>

        {/* Analytics Panel */}
        <div className="grid grid-cols-2 gap-6">
          {/* Cost Breakdown */}
          <div className="border border-zinc-700/40 rounded-2xl bg-zinc-900/30 p-5">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">Cost Breakdown</h3>
            <div className="space-y-3">
              {costBars.map((bar) => (
                <div key={bar.label} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-zinc-400">{bar.label}</span>
                    <span className="text-white font-mono">${bar.value.toFixed(0)}</span>
                  </div>
                  <div className="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full rounded-full ${bar.color}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.max(1, (bar.value / maxCost) * 100)}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-zinc-800 space-y-2 text-sm">
              <div className="flex justify-between text-zinc-400">
                <span>Subtotal (ex margin)</span>
                <span className="text-white font-mono">${totals.subtotal.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Margin ({marginPercent}%)</span>
                <span className="text-white font-mono">${totals.margin.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>Ex GST</span>
                <span className="text-white font-mono">${totals.exGst.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-zinc-400">
                <span>GST (10%)</span>
                <span className="text-white font-mono">${totals.gst.toFixed(2)}</span>
              </div>
              <div className="flex justify-between text-white font-semibold text-base pt-2 border-t border-zinc-700">
                <span>Total (inc GST)</span>
                <span className="text-amber-400 font-mono">${totals.total.toFixed(2)}</span>
              </div>
            </div>
          </div>

          {/* Per-Room Breakdown */}
          <div className="border border-zinc-700/40 rounded-2xl bg-zinc-900/30 p-5">
            <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">Room Breakdown</h3>
            <div className="space-y-2">
              <div className="grid grid-cols-5 text-xs text-zinc-500 uppercase tracking-wider pb-2 border-b border-zinc-800">
                <span>Room</span>
                <span className="text-right">Walls</span>
                <span className="text-right">Ceiling</span>
                <span className="text-right">Cornice</span>
                <span className="text-right">Total</span>
              </div>
              {rooms.map((room) => {
                const a = calcRoomAreas(room);
                const wc = a.netWallArea * WALL_FINISHES[room.wallFinish].rate;
                const cc = a.ceilingArea * CEILING_FINISHES[room.ceilingFinish].rate;
                const co = a.corniceLength * CORNICE_RATES[room.corniceType].rate;
                return (
                  <div key={room.id} className="grid grid-cols-5 text-sm py-1.5 border-b border-zinc-800/50">
                    <span className="text-zinc-300 truncate">{room.name}</span>
                    <span className="text-right font-mono text-zinc-400">${wc.toFixed(0)}</span>
                    <span className="text-right font-mono text-zinc-400">${cc.toFixed(0)}</span>
                    <span className="text-right font-mono text-zinc-400">${co.toFixed(0)}</span>
                    <span className="text-right font-mono text-white">${(wc + cc + co).toFixed(0)}</span>
                  </div>
                );
              })}
            </div>

            {/* Labour Estimate */}
            <div className="mt-4 pt-4 border-t border-zinc-800">
              <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Labour Estimate</h4>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Est. Hours" value={totals.labourEstimate.toFixed(1)} unit="hrs" />
                <Stat label="Labour Cost" value={`$${totals.labourCost.toFixed(0)}`} unit={`@$${LABOUR_RATE_HR}/hr`} />
              </div>
            </div>
          </div>
        </div>

        {/* Materials Takeoff */}
        <AnimatePresence>
          {showMaterials && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="border border-zinc-700/40 rounded-2xl bg-zinc-900/30 p-5 overflow-hidden"
            >
              <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-4">
                Materials Takeoff (inc. {((WASTE_FACTOR - 1) * 100).toFixed(0)}% waste)
              </h3>
              <div className="space-y-1">
                <div className="grid grid-cols-5 text-xs text-zinc-500 uppercase tracking-wider pb-2 border-b border-zinc-800">
                  <span className="col-span-2">Item</span>
                  <span className="text-right">Qty</span>
                  <span className="text-right">Unit Cost</span>
                  <span className="text-right">Total</span>
                </div>
                {materials.map((m, i) => (
                  <div key={i} className="grid grid-cols-5 text-sm py-1.5 border-b border-zinc-800/50">
                    <span className="col-span-2 text-zinc-300">{m.name}</span>
                    <span className="text-right font-mono text-zinc-400">
                      {m.qty} {m.unit}
                    </span>
                    <span className="text-right font-mono text-zinc-400">${m.unitCost.toFixed(2)}</span>
                    <span className="text-right font-mono text-white">${m.total.toFixed(2)}</span>
                  </div>
                ))}
                <div className="grid grid-cols-5 text-sm py-2 font-semibold">
                  <span className="col-span-4 text-zinc-300">Materials Total</span>
                  <span className="text-right font-mono text-amber-400">${materialTotal.toFixed(2)}</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Rate Reference */}
        <div className="border border-zinc-700/40 rounded-2xl bg-zinc-900/30 p-5 print:hidden">
          <h3 className="text-sm font-semibold text-zinc-300 uppercase tracking-wider mb-3">Rate Reference (AUD 2026)</h3>
          <div className="grid grid-cols-3 gap-6 text-xs">
            <div>
              <h4 className="text-amber-400 font-semibold mb-2">Wall Finishes</h4>
              {Object.values(WALL_FINISHES).filter(v => v.rate > 0).map((v) => (
                <div key={v.label} className="flex justify-between py-0.5 text-zinc-400">
                  <span>{v.label}</span>
                  <span className="font-mono text-zinc-300">${v.rate}{v.unit}</span>
                </div>
              ))}
            </div>
            <div>
              <h4 className="text-emerald-400 font-semibold mb-2">Ceiling Finishes</h4>
              {Object.values(CEILING_FINISHES).filter(v => v.rate > 0).map((v) => (
                <div key={v.label} className="flex justify-between py-0.5 text-zinc-400">
                  <span>{v.label}</span>
                  <span className="font-mono text-zinc-300">${v.rate}{v.unit}</span>
                </div>
              ))}
            </div>
            <div>
              <h4 className="text-purple-400 font-semibold mb-2">Cornice</h4>
              {Object.values(CORNICE_RATES).filter(v => v.rate > 0).map((v) => (
                <div key={v.label} className="flex justify-between py-0.5 text-zinc-400">
                  <span>{v.label}</span>
                  <span className="font-mono text-zinc-300">${v.rate}{v.unit}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-zinc-600 py-4 print:hidden">
          Plaster Estimator &middot; plaster.qbc.network &middot; Rates are indicative — always verify with local suppliers
        </div>
      </div>

      {/* Print styles handled via Tailwind print: variants */}
    </div>
  );
}
