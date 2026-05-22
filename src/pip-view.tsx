import { useRef } from "react";

import { clamp } from "./presets";
import { store, useStore } from "./store";

const HEADER_H = 28;
const RESIZE_HANDLE = 18;

export function PipView() {
  const s = useStore();
  const dragRef = useRef<{ x: number; y: number; gx: number; gy: number } | null>(null);
  const resizeRef = useRef<{ x: number; y: number; gw: number; gh: number } | null>(null);

  if (!s.visible || !s.url) return null;

  const onDragDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const cur = store.get().geom;
    dragRef.current = { x: e.clientX, y: e.clientY, gx: cur.x, gy: cur.y };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onDragMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const cur = store.get().geom;
    const dx = ((e.clientX - dragRef.current.x) / window.innerWidth) * 100;
    const dy = ((e.clientY - dragRef.current.y) / window.innerHeight) * 100;
    store.set({
      geom: clamp({ ...cur, x: dragRef.current.gx + dx, y: dragRef.current.gy + dy }),
    });
  };
  const onDragUp = () => {
    dragRef.current = null;
  };

  const onResizeDown = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const cur = store.get().geom;
    resizeRef.current = { x: e.clientX, y: e.clientY, gw: cur.w, gh: cur.h };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };
  const onResizeMove = (e: React.PointerEvent) => {
    if (!resizeRef.current) return;
    const cur = store.get().geom;
    const dw = ((e.clientX - resizeRef.current.x) / window.innerWidth) * 100;
    const dh = ((e.clientY - resizeRef.current.y) / window.innerHeight) * 100;
    store.set({
      geom: clamp({ ...cur, w: resizeRef.current.gw + dw, h: resizeRef.current.gh + dh }),
    });
  };
  const onResizeUp = () => {
    resizeRef.current = null;
  };

  return (
    <div
      style={{
        position: "absolute",
        left: `${s.geom.x}%`,
        top: `${s.geom.y}%`,
        width: `${s.geom.w}%`,
        height: `${s.geom.h}%`,
        opacity: s.opacity / 100,
        pointerEvents: s.clickThrough ? "none" : "auto",
        background: "#000",
        border: "1px solid #444",
        boxShadow: s.clickThrough
          ? "0 0 0 2px rgba(220,180,60,0.45), 0 4px 16px rgba(0,0,0,0.6)"
          : "0 4px 16px rgba(0,0,0,0.6)",
        borderRadius: 6,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        transition: "opacity 200ms",
      }}
    >
      <div
        onPointerDown={onDragDown}
        onPointerMove={onDragMove}
        onPointerUp={onDragUp}
        style={{
          height: HEADER_H,
          background: "linear-gradient(180deg, #2a2a2a, #181818)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06)",
          color: "#aaa",
          cursor: "move",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          paddingLeft: 8,
          fontSize: 12,
          userSelect: "none",
        }}
      >
        DeckPiP{s.clickThrough ? " · click-through" : ""}
      </div>
      <iframe
        src={s.url}
        sandbox="allow-scripts allow-forms allow-pointer-lock allow-same-origin"
        referrerPolicy="no-referrer"
        style={{ flex: 1, border: "none", background: "#000" }}
      />
      <div
        onPointerDown={onResizeDown}
        onPointerMove={onResizeMove}
        onPointerUp={onResizeUp}
        style={{
          position: "absolute",
          right: 0,
          bottom: 0,
          width: RESIZE_HANDLE,
          height: RESIZE_HANDLE,
          cursor: "nwse-resize",
          background: "linear-gradient(135deg, transparent 50%, #888 50%)",
        }}
      />
    </div>
  );
}
