import { useRef } from "react";
import { FaTv } from "react-icons/fa";

import { clamp, snapToEdges } from "./presets";
import { store, useStore } from "./store";

const HEADER_NORMAL = 28;
const HEADER_TOUCH = 50;
const HANDLE_NORMAL = 18;
const HANDLE_TOUCH = 36;
const BADGE_SIZE = 44;

/** Tiny clickable indicator shown when the session is alive but the user
 * has F10-hidden the overlay. Tap to bring it back. */
function MiniBadge() {
  return (
    <button
      onClick={() => store.set({ visible: true }, false)}
      style={{
        position: "absolute",
        right: 12,
        bottom: 12,
        width: BADGE_SIZE,
        height: BADGE_SIZE,
        borderRadius: BADGE_SIZE / 2,
        border: "1px solid rgba(255,255,255,0.2)",
        background: "rgba(20,20,20,0.85)",
        color: "#bbb",
        cursor: "pointer",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "0 4px 14px rgba(0,0,0,0.5)",
        backdropFilter: "blur(4px)",
        fontSize: 18,
        padding: 0,
        pointerEvents: "auto",
      }}
      title="Show DeckPiP overlay"
    >
      <FaTv />
    </button>
  );
}

export function PipView() {
  const s = useStore();
  const dragRef = useRef<{ x: number; y: number; gx: number; gy: number } | null>(null);
  const resizeRef = useRef<{ x: number; y: number; gw: number; gh: number } | null>(null);

  // No active session: render nothing.
  if (!s.url) return null;

  // Session is alive but the user hid the overlay — show the mini-badge so
  // they can recover without going through Quick Access.
  if (!s.visible) return <MiniBadge />;

  const headerH = s.touchMode ? HEADER_TOUCH : HEADER_NORMAL;
  const handle = s.touchMode ? HANDLE_TOUCH : HANDLE_NORMAL;

  const onDragDown = (e: React.PointerEvent) => {
    if (s.locked) return;
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
    if (dragRef.current) {
      store.set({ geom: snapToEdges(store.get().geom) });
    }
    dragRef.current = null;
  };

  const onResizeDown = (e: React.PointerEvent) => {
    if (s.locked) return;
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
          height: headerH,
          background: "linear-gradient(180deg, #2a2a2a, #181818)",
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06)",
          color: "#aaa",
          cursor: s.locked ? "default" : "move",
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          paddingLeft: 8,
          fontSize: s.touchMode ? 14 : 12,
          userSelect: "none",
        }}
      >
        DeckPiP
        {s.clickThrough ? " · click-through" : ""}
        {s.locked ? " · 🔒" : ""}
      </div>
      <iframe
        src={s.url}
        sandbox="allow-scripts allow-forms allow-pointer-lock allow-same-origin"
        referrerPolicy="no-referrer"
        style={{ flex: 1, border: "none", background: "#000" }}
      />
      {!s.locked && (
        <div
          onPointerDown={onResizeDown}
          onPointerMove={onResizeMove}
          onPointerUp={onResizeUp}
          style={{
            position: "absolute",
            right: 0,
            bottom: 0,
            width: handle,
            height: handle,
            cursor: "nwse-resize",
            background: "linear-gradient(135deg, transparent 50%, #888 50%)",
          }}
        />
      )}
    </div>
  );
}
