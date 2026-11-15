export function clamp01(value: number): number {
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

export function progress(frame: number, start: number, window: number): number {
  if (window <= 0) return frame >= start ? 1 : 0;
  return clamp01((frame - start) / window);
}

export function easeOutCubic(t: number): number {
  const x = clamp01(t);
  return 1 - (1 - x) ** 3;
}

export function easeInOutCubic(t: number): number {
  const x = clamp01(t);
  return x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2;
}

export function lerp(from: number, to: number, t: number): number {
  return from + (to - from) * clamp01(t);
}

export const FRAMES = {
  reveal: 12,
  hide: 12,
  move: 24,
  draw: 24,
  count: 12,
  grow: 18,
  highlightUp: 12,
  highlightDown: 12
} as const;
