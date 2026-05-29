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

/**
 * Aero-style snap: if the geom is within `threshold` percent of any
 * of the 9 reference points (4 corners, 4 edge-centers, screen-center),
 * snap to that point. Same applies to the right/bottom edges.
 */
export function snapToEdges(g: Geom, threshold = 5): Geom {
  const snap = (v: number, target: number): number =>
    Math.abs(v - target) <= threshold ? target : v;

  let x = snap(g.x, 0);
  x = snap(x, (100 - g.w) / 2);
  x = snap(x, 100 - g.w);

  let y = snap(g.y, 0);
  y = snap(y, (100 - g.h) / 2);
  y = snap(y, 100 - g.h);

  return clamp({ ...g, x, y });
}
