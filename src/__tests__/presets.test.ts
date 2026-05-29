import { describe, expect, it } from "vitest";

import { clamp, PRESETS, snapToEdges } from "../presets";

describe("PRESETS", () => {
  it("all presets stay within 0..100 bounds", () => {
    for (const [, g] of Object.entries(PRESETS)) {
      expect(g.x + g.w).toBeLessThanOrEqual(100);
      expect(g.y + g.h).toBeLessThanOrEqual(100);
      expect(g.w).toBeGreaterThanOrEqual(15);
      expect(g.h).toBeGreaterThanOrEqual(15);
    }
  });
});

describe("clamp", () => {
  it("keeps an in-bounds geom unchanged", () => {
    const g = { x: 10, y: 20, w: 30, h: 40 };
    expect(clamp(g)).toEqual(g);
  });

  it("pulls negative x/y to zero", () => {
    expect(clamp({ x: -5, y: -10, w: 30, h: 30 })).toMatchObject({ x: 0, y: 0 });
  });

  it("prevents the overlay from leaving the right edge", () => {
    const result = clamp({ x: 80, y: 10, w: 30, h: 30 });
    expect(result.x + result.w).toBeLessThanOrEqual(100);
  });

  it("clamps width and height to the minimum of 15", () => {
    expect(clamp({ x: 0, y: 0, w: 5, h: 8 }).w).toBe(15);
    expect(clamp({ x: 0, y: 0, w: 5, h: 8 }).h).toBe(15);
  });

  it("clamps width and height to the maximum of 100", () => {
    expect(clamp({ x: 0, y: 0, w: 200, h: 300 }).w).toBe(100);
    expect(clamp({ x: 0, y: 0, w: 200, h: 300 }).h).toBe(100);
  });
});

describe("snapToEdges", () => {
  it("snaps to left edge when within threshold", () => {
    const out = snapToEdges({ x: 2, y: 50, w: 30, h: 30 });
    expect(out.x).toBe(0);
  });

  it("snaps to right edge when within threshold", () => {
    const out = snapToEdges({ x: 68, y: 50, w: 30, h: 30 });
    // 100 - 30 = 70, distance to 68 is 2 < threshold 5
    expect(out.x).toBe(70);
  });

  it("snaps to horizontal center", () => {
    const out = snapToEdges({ x: 36, y: 50, w: 30, h: 30 });
    // (100-30)/2 = 35
    expect(out.x).toBe(35);
  });

  it("leaves far-from-edge alone", () => {
    const out = snapToEdges({ x: 20, y: 20, w: 30, h: 30 });
    expect(out.x).toBe(20);
    expect(out.y).toBe(20);
  });

  it("respects custom threshold", () => {
    expect(snapToEdges({ x: 8, y: 50, w: 30, h: 30 }, 5).x).toBe(8);
    expect(snapToEdges({ x: 8, y: 50, w: 30, h: 30 }, 10).x).toBe(0);
  });
});
