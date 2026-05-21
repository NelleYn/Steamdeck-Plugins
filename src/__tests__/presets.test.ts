import { describe, expect, it } from "vitest";

import { clamp, PRESETS } from "../presets";

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
