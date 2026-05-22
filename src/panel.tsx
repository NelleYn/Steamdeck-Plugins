import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  SliderField,
  TextField,
  ToggleField,
  Navigation,
} from "@decky/ui";
import { routerHook, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaTimes } from "react-icons/fa";

import {
  AppEntry,
  DepStatus,
  addCustomApp,
  checkDeps,
  installDeps,
  listApps,
  removeCustomApp,
  startMirror,
  startPip,
  stopMirror,
  stopPip,
} from "./api";
import { friendlyError } from "./errors";
import { PipView } from "./pip-view";
import { PRESETS } from "./presets";
import { ensureHydrated, store, useStore } from "./store";

export const ROUTE = "/deckpip/view";

function depsLabel(deps: DepStatus | null): string {
  if (!deps) return "Check dependencies";
  const missing = Object.entries(deps)
    .filter(([, ok]) => !ok)
    .map(([k]) => k);
  return missing.length === 0 ? "Dependencies OK" : `Missing: ${missing.join(", ")}`;
}

function openRoute(url: string) {
  store.set({ url, visible: true });
  try {
    routerHook.removeRoute(ROUTE);
  } catch {
    // route may not be registered
  }
  routerHook.addRoute(ROUTE, () => <PipView />, { exact: true });
  Navigation.Navigate(ROUTE);
  Navigation.CloseSideMenus();
}

function closeRoute() {
  try {
    routerHook.removeRoute(ROUTE);
  } catch {
    // already gone
  }
  store.set({ url: "", visible: true, mirrorOn: false }, false);
}

export function Content() {
  const s = useStore();
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [running, setRunning] = useState<{ id: string; label: string; audio_only: boolean } | null>(
    null,
  );
  const [deps, setDeps] = useState<DepStatus | null>(null);
  const [installing, setInstalling] = useState(false);
  const [busy, setBusy] = useState(false);
  const [audioOnlyOnStart, setAudioOnlyOnStart] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [newAppLabel, setNewAppLabel] = useState("");
  const [newAppCmd, setNewAppCmd] = useState("");

  useEffect(() => {
    ensureHydrated();
    listApps().then(setApps);
    checkDeps().then(setDeps);
  }, []);

  const refreshApps = async () => setApps(await listApps());

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

  const onStart = async (app: AppEntry, audioOnly: boolean) => {
    setBusy(true);
    const res = await startPip(app.id, audioOnly);
    setBusy(false);
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
      return;
    }
    setRunning({ id: app.id, label: app.label, audio_only: audioOnly });
    if (!audioOnly && res.url) {
      openRoute(res.url);
    } else {
      toaster.toast({ title: "DeckPiP", body: `${app.label}: audio-only session running` });
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
    const url = webUrl.trim();
    if (!url) {
      toaster.toast({ title: "DeckPiP", body: "Enter a URL first" });
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      toaster.toast({ title: "DeckPiP", body: "Only http(s) URLs are allowed" });
      return;
    }
    openRoute(url);
  };

  const onToggleMirror = async () => {
    if (store.get().mirrorOn) {
      await stopMirror();
      store.set({ mirrorOn: false }, false);
    } else {
      const res = await startMirror();
      if (!res.ok) {
        toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
        return;
      }
      store.set({ mirrorOn: true }, false);
      toaster.toast({ title: "DeckPiP", body: "GameMirror window created in Xvnc :42" });
    }
  };

  const onAddApp = async () => {
    if (!newAppLabel.trim() || !newAppCmd.trim()) return;
    const suffix =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().slice(0, 8)
        : Math.random().toString(36).slice(2, 10);
    const id = `custom_${suffix}`;
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
      <PanelSection title={`DeckPiP — ${running.label}`}>
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
                onChange={(v) => store.set({ visible: v }, false)}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Click-through"
                description="Mouse/touch passes to game"
                checked={s.clickThrough}
                onChange={(v) => store.set({ clickThrough: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Opacity"
                value={s.opacity}
                min={20}
                max={100}
                step={5}
                onChange={(v) => store.set({ opacity: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => store.set({ geom: PRESETS["small-br"] })}>
                Preset: small bottom-right
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => store.set({ geom: PRESETS["medium-l"] })}>
                Preset: medium left
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={() => store.set({ geom: PRESETS.full })}>
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
              onClick={() => onStart(app, audioOnlyOnStart)}
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
