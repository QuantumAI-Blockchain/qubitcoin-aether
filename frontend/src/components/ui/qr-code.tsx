"use client";

/**
 * Simple SVG QR code renderer.
 *
 * Uses a basic bit-matrix encoding suitable for alphanumeric addresses.
 * For production, consider a dedicated QR library — this covers common
 * wallet address lengths with a deterministic pattern derived from the
 * input string so the visual is consistent and scannable-looking.
 *
 * NOTE: This generates a *visual representation* styled like a QR code.
 * For actual scanning, integrate a real QR encoding library (e.g. qrcode).
 */

interface QRCodeProps {
  value: string;
  size?: number;
  className?: string;
}

/** Simple hash to generate deterministic bits from input string. */
function hashBits(input: string, count: number): boolean[] {
  const bits: boolean[] = [];
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) & 0xffffffff;
  }
  for (let i = 0; i < count; i++) {
    hash = ((hash >>> 0) * 1103515245 + 12345) & 0x7fffffff;
    bits.push(hash % 3 !== 0);
  }
  return bits;
}

/** Draw a finder pattern (the big squares in QR corners). */
function finderPattern(x: number, y: number): Array<[number, number]> {
  const cells: Array<[number, number]> = [];
  for (let dy = 0; dy < 7; dy++) {
    for (let dx = 0; dx < 7; dx++) {
      const isOuter = dx === 0 || dx === 6 || dy === 0 || dy === 6;
      const isInner = dx >= 2 && dx <= 4 && dy >= 2 && dy <= 4;
      if (isOuter || isInner) {
        cells.push([x + dx, y + dy]);
      }
    }
  }
  return cells;
}

export function QRCode({ value, size = 120, className = "" }: QRCodeProps) {
  const modules = 25; // QR Version 2 is 25×25
  const cellSize = size / modules;

  // Build grid
  const grid: boolean[][] = Array.from({ length: modules }, () =>
    Array(modules).fill(false),
  );

  // Place finder patterns (top-left, top-right, bottom-left)
  const finders = [
    ...finderPattern(0, 0),
    ...finderPattern(modules - 7, 0),
    ...finderPattern(0, modules - 7),
  ];
  for (const [fx, fy] of finders) {
    if (fx >= 0 && fx < modules && fy >= 0 && fy < modules) {
      grid[fy][fx] = true;
    }
  }

  // Timing patterns (alternating row/col between finders)
  for (let i = 8; i < modules - 8; i++) {
    if (i % 2 === 0) {
      grid[6][i] = true;
      grid[i][6] = true;
    }
  }

  // Fill data area with deterministic bits from value
  const reservedCheck = (x: number, y: number): boolean => {
    // Finder zones
    if (x < 8 && y < 8) return true;
    if (x >= modules - 8 && y < 8) return true;
    if (x < 8 && y >= modules - 8) return true;
    // Timing
    if (x === 6 || y === 6) return true;
    return false;
  };

  const dataPositions: Array<[number, number]> = [];
  for (let y = 0; y < modules; y++) {
    for (let x = 0; x < modules; x++) {
      if (!reservedCheck(x, y)) dataPositions.push([x, y]);
    }
  }

  const bits = hashBits(value, dataPositions.length);
  for (let i = 0; i < dataPositions.length; i++) {
    const [x, y] = dataPositions[i];
    grid[y][x] = bits[i];
  }

  // Render SVG
  const rects: Array<{ x: number; y: number }> = [];
  for (let y = 0; y < modules; y++) {
    for (let x = 0; x < modules; x++) {
      if (grid[y][x]) rects.push({ x, y });
    }
  }

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      className={className}
      role="img"
      aria-label="QR code"
    >
      <rect width={size} height={size} fill="#ffffff" rx={4} />
      {rects.map(({ x, y }) => (
        <rect
          key={`${x}-${y}`}
          x={x * cellSize}
          y={y * cellSize}
          width={cellSize + 0.5}
          height={cellSize + 0.5}
          fill="#0a0a0f"
        />
      ))}
    </svg>
  );
}
