export type Geom = { x: number; y: number; w: number; h: number };
export type PresetId = "small-br" | "medium-l" | "full";

export const PRESETS: Record<PresetId, Geom> = {
  "small-br": { x: 62, y: 55, w: 36, h: 42 },
  "medium-l": { x: 4, y: 8, w: 46, h: 84 },
  full: { x: 0, y: 0, w: 100, h: 100 },
};

export function clamp(g: Geom): Geom {
  const w = Math.max(15, Math.min(100, g.w));
  const h = Math.max(15, Math.min(100, g.h));
  return {
    w,
    h,
    x: Math.max(0, Math.min(100 - w, g.x)),
    y: Math.max(0, Math.min(100 - h, g.y)),
  };
}
