import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  TextField,
  ToggleField,
  Navigation,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, routerHook, toaster } from "@decky/api";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { FaTv, FaTimes } from "react-icons/fa";

// ---- backend bindings -----------------------------------------------------

type AppEntry = { id: string; label: string };
type StartResult = { ok: boolean; url?: string; audio_only?: boolean; error?: string };
type DepStatus = Record<string, boolean>;
type InstallResult = { ok: boolean; rc?: number; stdout?: string; stderr?: string; error?: string };
type SimpleResult = { ok: boolean; error?: string };

const listApps = callable<[], AppEntry[]>("list_apps");
const checkDeps = callable<[], DepStatus>("check_dependencies");
const installDeps = callable<[], InstallResult>("install_dependencies");
const startPip = callable<[app_id: string, audio_only: boolean], StartResult>("start_pip");
const stopPip = callable<[], SimpleResult>("stop_pip");
const settingsGet = callable<[key: string, dflt: any], any>("settings_get");
const settingsSet = callable<[key: string, value: any], SimpleResult>("settings_set");
const addCustomApp = callable<[id: string, label: string, command: string], SimpleResult>("add_custom_app");
const removeCustomApp = callable<[id: string], SimpleResult>("remove_custom_app");
const startMirror = callable<[], SimpleResult>("start_game_mirror");
const stopMirror = callable<[], SimpleResult>("stop_game_mirror");

const ROUTE = "/deckpip/view";
const SETTINGS_KEY = "ui_state_v1";

// ---- presets & geometry ---------------------------------------------------

type Geom = { x: number; y: number; w: number; h: number };
type PresetId = "small-br" | "medium-l" | "full";

const PRESETS: Record<PresetId, Geom> = {
  "small-br": { x: 62, y: 55, w: 36, h: 42 },
  "medium-l": { x: 4, y: 8, w: 46, h: 84 },
  "full": { x: 0, y: 0, w: 100, h: 100 },
};

// ---- external store with useSyncExternalStore -----------------------------

type Persisted = {
  geom: Geom;
  opacity: number;
  clickThrough: boolean;
};

type State = Persisted & {
  url: string;
  visible: boolean;
  mirrorOn: boolean;
};

const DEFAULT_STATE: State = {
  url: "",
  geom: PRESETS["small-br"],
  opacity: 95,
  clickThrough: false,
  visible: true,
  mirrorOn: false,
};

let state: State = { ...DEFAULT_STATE };
const listeners = new Set<() => void>();
const emit = () => listeners.forEach((l) => l());
const setState = (patch: Partial<State>, persist = true) => {
  state = { ...state, ...patch };
  emit();
  if (persist) {
    const p: Persisted = {
      geom: state.geom,
      opacity: state.opacity,
      clickThrough: state.clickThrough,
    };
    settingsSet(SETTINGS_KEY, p).catch(() => {});
  }
};
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};
const getSnapshot = () => state;
const useStore = () => useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

let settingsLoaded = false;
const ensureSettingsLoaded = async () => {
  if (settingsLoaded) return;
  settingsLoaded = true;
  const p = (await settingsGet(SETTINGS_KEY, null).catch(() => null)) as Persisted | null;
  if (p && p.geom && typeof p.opacity === "number") {
    setState({ geom: p.geom, opacity: p.opacity, clickThrough: !!p.clickThrough }, false);
  }
};

// ---- PiP overlay component ------------------------------------------------

const HEADER_H = 28;
const RESIZE_HANDLE = 18;

function PipView() {
  const s = useStore();
  const dragRef = useRef<{ x: number; y: number; gx: number; gy: number } | null>(null);
  const resizeRef = useRef<{ x: number; y: number; gw: number; gh: number } | null>(null);

  if (!s.visible || !s.url) return null;

  const clamp = (g: Geom): Geom => ({
    x: Math.max(0, Math.min(100 - g.w, g.x)),
    y: Math.max(0, Math.min(100 - g.h, g.y)),
    w: Math.max(15, Math.min(100, g.w)),
    h: Math.max(15, Math.min(100, g.h)),
  });

  const onDragDown = (e: React.PointerEvent) => {
    e.preventDefault();
    dragRef.current = { x: e.clientX, y: e.clientY, gx: state.geom.x, gy: state.geom.y };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onDragMove = (e: React.PointerEvent) => {
    if (!dragRef.current) return;
    const dx = ((e.clientX - dragRef.current.x) / window.innerWidth) * 100;
    const dy = ((e.clientY - dragRef.current.y) / window.innerHeight) * 100;
    setState({
      geom: clamp({ ...state.geom, x: dragRef.current.gx + dx, y: dragRef.current.gy + dy }),
    });
  };
  const onDragUp = () => {
    dragRef.current = null;
  };

  const onResizeDown = (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    resizeRef.current = { x: e.clientX, y: e.clientY, gw: state.geom.w, gh: state.geom.h };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onResizeMove = (e: React.PointerEvent) => {
    if (!resizeRef.current) return;
    const dw = ((e.clientX - resizeRef.current.x) / window.innerWidth) * 100;
    const dh = ((e.clientY - resizeRef.current.y) / window.innerHeight) * 100;
    setState({
      geom: clamp({ ...state.geom, w: resizeRef.current.gw + dw, h: resizeRef.current.gh + dh }),
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
        border: s.clickThrough ? "2px dashed #aa5" : "1px solid #444",
        borderRadius: 6,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        boxShadow: "0 4px 16px rgba(0,0,0,0.6)",
      }}
    >
      <div
        onPointerDown={onDragDown}
        onPointerMove={onDragMove}
        onPointerUp={onDragUp}
        style={{
          height: HEADER_H,
          background: "#222",
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
      <iframe src={s.url} style={{ flex: 1, border: "none", background: "#000" }} />
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

// ---- error -> friendly text -----------------------------------------------

function friendlyError(err: string | undefined): string {
  if (!err) return "Unknown error";
  if (err === "already_running") return "Session is already running";
  if (err === "no_session") return "Start a PiP session first";
  if (err === "already_mirroring") return "Game mirror already running";
  if (err === "no_gamescope_pw_node") return "Gamescope PipeWire node not found (game not running?)";
  if (err.startsWith("missing_dependency:")) {
    const dep = err.split(":")[1] ?? "?";
    if (dep === "Xvnc" || dep === "vncpasswd")
      return "TigerVNC missing — tap Install dependencies";
    if (dep === "novnc") return "noVNC missing — tap Install dependencies";
    if (dep === "websockify") return "websockify missing — tap Install dependencies";
    if (dep === "gstreamer") return "gstreamer missing — sudo pacman -S gst-plugins-good gst-plugin-pipewire";
    return `Missing: ${dep}`;
  }
  if (err.startsWith("parse_error:")) return `Could not parse command: ${err.split(":").slice(1).join(":")}`;
  return err;
}

// ---- Panel UI -------------------------------------------------------------

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
  const [busy, setBusy] = useState(false);
  const [audioOnlyOnStart, setAudioOnlyOnStart] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [newAppLabel, setNewAppLabel] = useState("");
  const [newAppCmd, setNewAppCmd] = useState("");

  useEffect(() => {
    ensureSettingsLoaded();
    listApps().then(setApps);
    checkDeps().then(setDeps);
  }, []);

  const refreshApps = async () => setApps(await listApps());

  const openRoute = (url: string) => {
    setState({ url, visible: true });
    try {
      routerHook.removeRoute(ROUTE);
    } catch {}
    routerHook.addRoute(ROUTE, () => <PipView />, { exact: true });
    Navigation.Navigate(ROUTE);
    Navigation.CloseSideMenus();
  };

  const closeRoute = () => {
    try {
      routerHook.removeRoute(ROUTE);
    } catch {}
    setState({ url: "", visible: true, mirrorOn: false }, false);
  };

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
    setBusy(true);
    const res = await startPip(appId, audioOnly);
    setBusy(false);
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
      return;
    }
    setRunning({ id: appId, audio_only: audioOnly });
    if (!audioOnly && res.url) {
      openRoute(res.url);
    } else {
      toaster.toast({ title: "DeckPiP", body: "Audio-only session running" });
    }
  };

  const onStop = async () => {
    setBusy(true);
    await stopPip();
    setBusy(false);
    closeRoute();
    setRunning(null);
  };

  const onOpenWebPip = () => {
    if (!webUrl.trim()) {
      toaster.toast({ title: "DeckPiP", body: "Enter a URL first" });
      return;
    }
    openRoute(webUrl.trim());
  };

  const onToggleMirror = async () => {
    if (state.mirrorOn) {
      await stopMirror();
      setState({ mirrorOn: false }, false);
    } else {
      const res = await startMirror();
      if (!res.ok) {
        toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
        return;
      }
      setState({ mirrorOn: true }, false);
      toaster.toast({ title: "DeckPiP", body: "GameMirror window created in Xvnc :42" });
    }
  };

  const onAddApp = async () => {
    if (!newAppLabel.trim() || !newAppCmd.trim()) return;
    const id = `custom_${Date.now().toString(36)}`;
    const res = await addCustomApp(id, newAppLabel.trim(), newAppCmd.trim());
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
      return;
    }
    setNewAppLabel("");
    setNewAppCmd("");
    await refreshApps();
  };

  const onRemoveApp = async (id: string) => {
    await removeCustomApp(id);
    await refreshApps();
  };

  if (running) {
    return (
      <PanelSection title={`DeckPiP — ${running.id}`}>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy} onClick={onStop}>
            {busy ? "Stopping…" : "Stop"}
          </ButtonItem>
        </PanelSectionRow>

        {running.id.startsWith("discord") && !running.audio_only && (
          <PanelSectionRow>
            <ToggleField
              label="Mirror game into Discord"
              description="Streams the game window to Xvnc so Discord can Go Live"
              checked={s.mirrorOn}
              onChange={onToggleMirror}
            />
          </PanelSectionRow>
        )}

        {!running.audio_only && (
          <>
            <PanelSectionRow>
              <ToggleField
                label="Visible"
                checked={s.visible}
                onChange={(v) => setState({ visible: v }, false)}
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
        <PanelSectionRow>
          <ToggleField
            label="Start audio-only"
            description="No iframe, just run guest with audio"
            checked={audioOnlyOnStart}
            onChange={setAudioOnlyOnStart}
          />
        </PanelSectionRow>
        {apps.map((app) => (
          <PanelSectionRow key={app.id}>
            <ButtonItem
              layout="below"
              disabled={busy}
              onClick={() => onStart(app.id, audioOnlyOnStart)}
            >
              {busy ? "Starting…" : app.label}
            </ButtonItem>
            {app.id.startsWith("custom_") && (
              <ButtonItem layout="below" onClick={() => onRemoveApp(app.id)}>
                <FaTimes /> remove
              </ButtonItem>
            )}
          </PanelSectionRow>
        ))}
      </PanelSection>

      <PanelSection title="Web PiP">
        <PanelSectionRow>
          <TextField
            label="URL"
            value={webUrl}
            onChange={(e) => setWebUrl((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onOpenWebPip}>
            Open URL in PiP
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="Custom app">
        <PanelSectionRow>
          <TextField
            label="Label"
            value={newAppLabel}
            onChange={(e) => setNewAppLabel((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Command (shlex-parsed)"
            value={newAppCmd}
            onChange={(e) => setNewAppCmd((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onAddApp}>
            Add
          </ButtonItem>
        </PanelSectionRow>
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

// ---- hotkey: F10 toggles visibility ---------------------------------------

const installHotkey = () => {
  const handler = (e: KeyboardEvent) => {
    if (e.key === "F10") {
      e.preventDefault();
      setState({ visible: !state.visible }, false);
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
};

export default definePlugin(() => {
  const removeHotkey = installHotkey();
  ensureSettingsLoaded();
  return {
    name: "DeckPiP",
    titleView: <div className={staticClasses.Title}>DeckPiP</div>,
    content: <Content />,
    icon: <FaTv />,
    onDismount() {
      try {
        routerHook.removeRoute(ROUTE);
      } catch {}
      removeHotkey();
    },
  };
});
