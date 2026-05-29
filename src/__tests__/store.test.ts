import { describe, expect, it, vi } from "vitest";

import { createStore, DEFAULT_STATE } from "../store-core";

describe("createStore", () => {
  it("starts with default state", () => {
    const s = createStore();
    expect(s.get()).toEqual(DEFAULT_STATE);
  });

  it("applies a patch", () => {
    const s = createStore();
    s.set({ opacity: 50 });
    expect(s.get().opacity).toBe(50);
    expect(s.get().visible).toBe(true);
  });

  it("notifies subscribers exactly once per set()", () => {
    const s = createStore();
    const cb = vi.fn();
    s.subscribe(cb);
    s.set({ opacity: 60 });
    s.set({ opacity: 70 });
    expect(cb).toHaveBeenCalledTimes(2);
  });

  it("calls the persist fn only when persist=true (default)", () => {
    const persist = vi.fn();
    const s = createStore(persist);
    s.set({ visible: false }, false);
    expect(persist).not.toHaveBeenCalled();
    s.set({ opacity: 80 });
    expect(persist).toHaveBeenCalledOnce();
    expect(persist).toHaveBeenCalledWith(
      expect.objectContaining({ opacity: 80, clickThrough: false, touchMode: false }),
    );
  });

  it("hydrates touchMode", () => {
    const s = createStore();
    s.hydrate({ touchMode: true });
    expect(s.get().touchMode).toBe(true);
  });

  it("persists and hydrates locked", () => {
    const persist = vi.fn();
    const s = createStore(persist);
    s.set({ locked: true });
    expect(persist).toHaveBeenCalledWith(expect.objectContaining({ locked: true }));
    const s2 = createStore();
    s2.hydrate({ locked: true });
    expect(s2.get().locked).toBe(true);
  });

  it("hydrate() merges only known persisted keys", () => {
    const s = createStore();
    s.set({ url: "http://before" }, false);
    s.hydrate({ opacity: 33, clickThrough: true });
    expect(s.get().opacity).toBe(33);
    expect(s.get().clickThrough).toBe(true);
    // Non-persisted fields are preserved.
    expect(s.get().url).toBe("http://before");
  });

  it("hydrate() ignores undefined slices", () => {
    const s = createStore();
    s.set({ opacity: 42 }, false);
    s.hydrate({});
    expect(s.get().opacity).toBe(42);
  });

  it("hydrate() rejects malformed geom", () => {
    const s = createStore();
    const before = s.get().geom;
    // @ts-expect-error -- intentionally wrong shape
    s.hydrate({ geom: "not an object" });
    expect(s.get().geom).toBe(before);
    // @ts-expect-error -- intentionally missing fields
    s.hydrate({ geom: { x: 1 } });
    expect(s.get().geom).toBe(before);
  });

  it("unsubscribe stops further notifications", () => {
    const s = createStore();
    const cb = vi.fn();
    const off = s.subscribe(cb);
    off();
    s.set({ visible: false });
    expect(cb).not.toHaveBeenCalled();
  });
});
