import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  ToggleField,
  Navigation,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, routerHook, toaster } from "@decky/api";
import { useEffect, useRef, useState } from "react";
import { FaTv } from "react-icons/fa";

type AppEntry = { id: string; label: string };
type StartResult = { ok: boolean; url?: string; audio_only?: boolean; error?: string };
type DepStatus = Record<string, boolean>;
type InstallResult = { ok: boolean; rc?: number; stdout?: string; stderr?: string; error?: string };

const listApps = callable<[], AppEntry[]>("list_apps");
const checkDeps = callable<[], DepStatus>("check_dependencies");
const installDeps = callable<[], InstallResult>("install_dependencies");
const startPip = callable<[app_id: string, audio_only: boolean], StartResult>("start_pip");
const stopPip = callable<[], { ok: boolean }>("stop_pip");

const ROUTE = "/deckpip/view";

type Geom = { x: number; y: number; w: number; h: number };
type PresetId = "small-br" | "medium-l" | "full";

const PRESETS: Record<PresetId, Geom> = {
  "small-br": { x: 62, y: 55, w: 36, h: 42 },
  "medium-l": { x: 4, y: 8, w: 46, h: 84 },
  "full": { x: 0, y: 0, w: 100, h: 100 },
};

type State = {
  url: string;
  geom: Geom;
  opacity: number;
  clickThrough: boolean;
  visible: boolean;
};

let state: State = {
  url: "",
  geom: PRESETS["small-br"],
  opacity: 95,
  clickThrough: false,
  visible: true,
};

const listeners = new Set<() => void>();
const setState = (patch: Partial<State>) => {
  state = { ...state, ...patch };
  listeners.forEach((l) => l());
};
const useStore = () => {
  const [, force] = useState(0);
  useEffect(() => {
    const cb = () => force((n) => n + 1);
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  }, []);
  return state;
};

function PipView() {
  const s = useStore();
  const drag = useRef<{ x: number; y: number; gx: number; gy: number } | null>(null);

  if (!s.visible || !s.url) return null;

  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    drag.current = { x: e.clientX, y: e.clientY, gx: state.geom.x, gy: state.geom.y };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current) return;
    const dx = ((e.clientX - drag.current.x) / window.innerWidth) * 100;
    const dy = ((e.clientY - drag.current.y) / window.innerHeight) * 100;
    setState({
      geom: {
        ...state.geom,
        x: Math.max(0, Math.min(100 - state.geom.w, drag.current.gx + dx)),
        y: Math.max(0, Math.min(100 - state.geom.h, drag.current.gy + dy)),
      },
    });
  };
  const onUp = () => {
    drag.current = null;
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
        borderRadius: 6,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
      }}
    >
      <div
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        style={{
          height: 16,
          background: "#222",
          cursor: "move",
          flexShrink: 0,
        }}
      />
      <iframe src={s.url} style={{ flex: 1, border: "none", background: "#000" }} />
    </div>
  );
}

function depsLabel(deps: DepStatus | null): string {
  if (!deps) return "Check dependencies";
  const missing = Object.entries(deps)
    .filter(([, ok]) => !ok)
    .map(([k]) => k);
  if (missing.length === 0) return "Dependencies OK";
  return `Missing: ${missing.join(", ")}`;
}

function Content() {
  const s = useStore();
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [running, setRunning] = useState<{ id: string; audio_only: boolean } | null>(null);
  const [deps, setDeps] = useState<DepStatus | null>(null);
  const [installing, setInstalling] = useState(false);

  useEffect(() => {
    listApps().then(setApps);
    checkDeps().then(setDeps);
  }, []);

  const onCheckDeps = async () => setDeps(await checkDeps());

  const onInstallDeps = async () => {
    setInstalling(true);
    const res = await installDeps();
    setInstalling(false);
    setDeps(await checkDeps());
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? "Dependencies installed" : `Install failed (rc=${res.rc ?? "?"})`,
    });
  };

  const onStart = async (appId: string, audioOnly: boolean) => {
    const res = await startPip(appId, audioOnly);
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: `Start failed: ${res.error ?? "unknown"}` });
      return;
    }
    setRunning({ id: appId, audio_only: audioOnly });
    if (!audioOnly && res.url) {
      setState({ url: res.url, visible: true });
      try {
        routerHook.removeRoute(ROUTE);
      } catch {}
      routerHook.addRoute(ROUTE, () => <PipView />, { exact: true });
      Navigation.Navigate(ROUTE);
      Navigation.CloseSideMenus();
    } else {
      toaster.toast({ title: "DeckPiP", body: "Audio-only session running" });
    }
  };

  const onStop = async () => {
    await stopPip();
    try {
      routerHook.removeRoute(ROUTE);
    } catch {}
    setState({ url: "", visible: true });
    setRunning(null);
  };

  if (running) {
    return (
      <PanelSection title={`DeckPiP — ${running.id}`}>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onStop}>
            Stop
          </ButtonItem>
        </PanelSectionRow>

        {!running.audio_only && (
          <>
            <PanelSectionRow>
              <ToggleField
                label="Visible"
                checked={s.visible}
                onChange={(v) => setState({ visible: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Click-through"
                description="Mouse/touch passes to game"
                checked={s.clickThrough}
                onChange={(v) => setState({ clickThrough: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Opacity"
                value={s.opacity}
                min={20}
                max={100}
                step={5}
                onChange={(v) => setState({ opacity: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => setState({ geom: PRESETS["small-br"] })}>
                Preset: small bottom-right
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => setState({ geom: PRESETS["medium-l"] })}>
                Preset: medium left
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => setState({ geom: PRESETS["full"] })}>
                Preset: fullscreen
              </ButtonItem>
            </PanelSectionRow>
          </>
        )}
      </PanelSection>
    );
  }

  return (
    <>
      <PanelSection title="Apps">
        {apps.map((app) => (
          <PanelSectionRow key={app.id}>
            <ButtonItem layout="below" onClick={() => onStart(app.id, false)}>
              {app.label}
            </ButtonItem>
          </PanelSectionRow>
        ))}
        {apps.map((app) => (
          <PanelSectionRow key={`${app.id}-audio`}>
            <ButtonItem layout="below" onClick={() => onStart(app.id, true)}>
              {app.label} — audio only
            </ButtonItem>
          </PanelSectionRow>
        ))}
      </PanelSection>

      <PanelSection title="System">
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onCheckDeps}>
            {depsLabel(deps)}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={installing} onClick={onInstallDeps}>
            {installing ? "Installing…" : "Install dependencies (pacman)"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}

export default definePlugin(() => {
  return {
    name: "DeckPiP",
    titleView: <div className={staticClasses.Title}>DeckPiP</div>,
    content: <Content />,
    icon: <FaTv />,
    onDismount() {
      try {
        routerHook.removeRoute(ROUTE);
      } catch {}
    },
  };
});
