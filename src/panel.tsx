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
  Bookmark,
  DepStatus,
  GameProfile,
  MprisPlayer,
  addBookmark,
  addCustomApp,
  checkDeps,
  checkUpdate,
  diagnostics,
  exportSettings,
  getProfile,
  LudusaviStatus,
  RcloneStatus,
  cloudSyncDown,
  cloudSyncUp,
  importSettings,
  installDeps,
  installEverything,
  installVendored,
  listApps,
  listBookmarks,
  ludusaviBackup,
  ludusaviFind,
  ludusaviInstall,
  ludusaviRestore,
  ludusaviStatus,
  mprisAction,
  mprisList,
  rcloneInstall,
  rcloneRemotes,
  rcloneStatus,
  removeBookmark,
  removeCustomApp,
  removeProfile,
  runUpdate,
  setGuestVolume,
  setProfile,
  settingsGet,
  settingsSet,
  startMirror,
  startNotificationMirror,
  startPip,
  stopMirror,
  stopNotificationMirror,
  stopPip,
} from "./api";
import { friendlyError } from "./errors";
import { PipView } from "./pip-view";
import { PRESETS } from "./presets";
import { getAppName } from "./steam";
import { ensureHydrated, store, useStore } from "./store";

export const ROUTE = "/deckpip/view";

function depsLabel(deps: DepStatus | null): string {
  if (!deps) return "Check dependencies";
  // Required keys have no leading underscore; optional keys start with `_optional_`.
  const required = Object.entries(deps).filter(([k]) => !k.startsWith("_optional_"));
  const optional = Object.entries(deps).filter(([k]) => k.startsWith("_optional_"));
  const missingReq = required.filter(([, ok]) => !ok).map(([k]) => k);
  const missingOpt = optional
    .filter(([, ok]) => !ok)
    .map(([k]) => k.replace(/^_optional_/, ""));
  if (missingReq.length > 0) return `Missing required: ${missingReq.join(", ")}`;
  if (missingOpt.length > 0) return `OK (GameMirror needs: ${missingOpt.join(", ")})`;
  return "Dependencies OK";
}

export function openRoute(url: string) {
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

export function closeRoute() {
  try {
    routerHook.removeRoute(ROUTE);
  } catch {
    // already gone
  }
  store.set({ url: "", visible: true, mirrorOn: false }, false);
}

/** Used both by the panel UI and by the auto-launch hook in index.tsx. */
export async function startFromUi(
  app: AppEntry,
  audioOnly: boolean,
): Promise<boolean> {
  const res = await startPip(app.id, audioOnly);
  if (!res.ok) {
    toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
    return false;
  }
  if (!audioOnly && res.url) {
    openRoute(res.url);
  } else {
    toaster.toast({ title: "DeckPiP", body: `${app.label}: audio-only session running` });
  }
  return true;
}

export function Content() {
  const s = useStore();
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [running, setRunning] = useState<{ id: string; label: string; audio_only: boolean } | null>(
    null,
  );
  const [deps, setDeps] = useState<DepStatus | null>(null);
  const [installing, setInstalling] = useState(false);
  const [installingVendored, setInstallingVendored] = useState(false);
  const [busy, setBusy] = useState(false);
  const [audioOnlyOnStart, setAudioOnlyOnStart] = useState(false);
  const [webUrl, setWebUrl] = useState("");
  const [newAppLabel, setNewAppLabel] = useState("");
  const [newAppCmd, setNewAppCmd] = useState("");
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [newBookmarkLabel, setNewBookmarkLabel] = useState("");
  const [newBookmarkUrl, setNewBookmarkUrl] = useState("");
  const [currentAppid, setCurrentAppid] = useState<number | null>(null);
  const [currentAppName, setCurrentAppName] = useState<string | null>(null);
  const [profile, setLocalProfile] = useState<GameProfile | null>(null);
  const [diag, setDiag] = useState<unknown | null>(null);
  const [updateInfo, setUpdateInfo] = useState<unknown | null>(null);
  const [githubToken, setGithubToken] = useState("");
  const [importPayload, setImportPayload] = useState("");
  const [guestVolume, setGuestVolumeUi] = useState(100);
  const [notifMirror, setNotifMirror] = useState(false);
  const [mprisPlayers, setMprisPlayers] = useState<MprisPlayer[]>([]);
  const [ludusavi, setLudusavi] = useState<LudusaviStatus | null>(null);
  const [ludusaviBusy, setLudusaviBusy] = useState<string | null>(null);
  const [ludusaviResult, setLudusaviResult] = useState<unknown>(null);
  const [autoBackup, setAutoBackup] = useState(false);
  const [rclone, setRclone] = useState<RcloneStatus | null>(null);
  const [rcloneBusy, setRcloneBusy] = useState<string | null>(null);
  const [rcloneRemoteList, setRcloneRemoteList] = useState<string[]>([]);
  const [cloudRemote, setCloudRemote] = useState("");
  const [cloudPath, setCloudPath] = useState("DeckPiP/backups");
  const [autoCloudSync, setAutoCloudSync] = useState(false);

  useEffect(() => {
    ensureHydrated();
    listApps().then(setApps);
    checkDeps().then(setDeps);
    listBookmarks().then(setBookmarks);
    ludusaviStatus().then(setLudusavi);
    rcloneStatus().then(setRclone);
    settingsGet("auto_backup_on_stop", false).then((v) => setAutoBackup(Boolean(v)));
    settingsGet("auto_cloud_sync", false).then((v) => setAutoCloudSync(Boolean(v)));
    settingsGet("cloud_remote", "").then((v) => setCloudRemote(typeof v === "string" ? v : ""));
    settingsGet("cloud_path", "DeckPiP/backups").then(
      (v) => setCloudPath(typeof v === "string" && v ? v : "DeckPiP/backups"),
    );
    settingsGet("github_token", "").then((v) => setGithubToken(typeof v === "string" ? v : ""));
    // Read current foreground appid out of the store; this is best-effort.
    const w = window as unknown as { __DECKPIP_CURRENT_APPID__?: number };
    const aid = w.__DECKPIP_CURRENT_APPID__ ?? null;
    if (aid) {
      setCurrentAppid(aid);
      setCurrentAppName(getAppName(aid));
      getProfile(String(aid)).then(setLocalProfile);
    }
  }, []);

  const refreshApps = async () => setApps(await listApps());
  const refreshBookmarks = async () => setBookmarks(await listBookmarks());

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

  const onInstallVendored = async () => {
    setInstallingVendored(true);
    const res = await installVendored(false);
    setInstallingVendored(false);
    setDeps(await checkDeps());
    const ok = (res as { ok?: boolean }).ok;
    toaster.toast({
      title: "DeckPiP",
      body: ok
        ? "noVNC + websockify vendored"
        : `Vendor install failed: ${JSON.stringify(res).slice(0, 160)}`,
    });
  };

  const onInstallEverything = async () => {
    setInstallingVendored(true);
    const res = await installEverything();
    setInstallingVendored(false);
    setDeps(await checkDeps());
    await refreshLudusavi();
    await refreshRclone();
    const ok = (res as { ok?: boolean }).ok;
    toaster.toast({
      title: "DeckPiP",
      body: ok
        ? "All vendored bundles installed (noVNC + websockify + Ludusavi + rclone)"
        : `Some installs failed — open Show diagnostics for details`,
    });
  };

  const onStart = async (app: AppEntry, audioOnly: boolean) => {
    setBusy(true);
    const ok = await startFromUi(app, audioOnly);
    setBusy(false);
    if (ok) setRunning({ id: app.id, label: app.label, audio_only: audioOnly });
  };

  const onStop = async () => {
    setBusy(true);
    await stopPip();
    setBusy(false);
    closeRoute();
    setRunning(null);
  };

  const onOpenWebPip = (url?: string) => {
    const target = (url ?? webUrl).trim();
    if (!target) {
      toaster.toast({ title: "DeckPiP", body: "Enter a URL first" });
      return;
    }
    if (!/^https?:\/\//i.test(target)) {
      toaster.toast({ title: "DeckPiP", body: "Only http(s) URLs are allowed" });
      return;
    }
    openRoute(target);
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

  const onAddBookmark = async () => {
    if (!newBookmarkLabel.trim() || !newBookmarkUrl.trim()) return;
    const suffix =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID().slice(0, 8)
        : Math.random().toString(36).slice(2, 10);
    const id = `bm_${suffix}`;
    const res = await addBookmark(id, newBookmarkLabel.trim(), newBookmarkUrl.trim());
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
      return;
    }
    setNewBookmarkLabel("");
    setNewBookmarkUrl("");
    await refreshBookmarks();
  };

  const onRemoveBookmark = async (id: string) => {
    await removeBookmark(id);
    await refreshBookmarks();
  };

  const onSaveProfile = async (autoLaunch: boolean) => {
    if (!currentAppid) {
      toaster.toast({ title: "DeckPiP", body: "No game in foreground" });
      return;
    }
    const cur = store.get();
    const next: GameProfile = {
      app_id: profile?.app_id ?? "discord_flatpak",
      audio_only: profile?.audio_only ?? false,
      auto_launch: autoLaunch,
      geom: cur.geom,
      opacity: cur.opacity,
    };
    await setProfile(String(currentAppid), next);
    setLocalProfile(next);
    toaster.toast({ title: "DeckPiP", body: "Profile saved" });
  };

  const onClearProfile = async () => {
    if (!currentAppid) return;
    await removeProfile(String(currentAppid));
    setLocalProfile(null);
  };

  const onExport = async () => {
    const res = await exportSettings();
    if (!res.ok || !res.data) {
      toaster.toast({ title: "DeckPiP", body: "Export failed" });
      return;
    }
    const text = JSON.stringify(res.data, null, 2);
    setImportPayload(text);
    try {
      // navigator.clipboard isn't reliable in Steam UI; show inline instead.
      await navigator.clipboard?.writeText?.(text);
      toaster.toast({ title: "DeckPiP", body: "Settings copied to clipboard" });
    } catch {
      toaster.toast({ title: "DeckPiP", body: "Settings shown below; copy manually" });
    }
  };

  const onImport = async () => {
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(importPayload);
    } catch (e) {
      toaster.toast({ title: "DeckPiP", body: `Invalid JSON: ${String(e).slice(0, 80)}` });
      return;
    }
    const res = await importSettings(parsed, true);
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? "Settings imported (merge)" : `Import failed: ${res.error ?? "?"}`,
    });
    if (res.ok) {
      setBookmarks(await listBookmarks());
      setApps(await listApps());
    }
  };

  const onChangeGuestVolume = async (v: number) => {
    setGuestVolumeUi(v);
    await setGuestVolume(v);
  };

  const onToggleNotifMirror = async (v: boolean) => {
    setNotifMirror(v);
    const res = v ? await startNotificationMirror() : await stopNotificationMirror();
    if (!res.ok) {
      toaster.toast({ title: "DeckPiP", body: friendlyError(res.error) });
      setNotifMirror(!v);
    }
  };

  const refreshMpris = async () => setMprisPlayers(await mprisList());

  const refreshLudusavi = async () => setLudusavi(await ludusaviStatus());

  const onLudusaviInstall = async () => {
    setLudusaviBusy("install");
    const res = await ludusaviInstall(false);
    setLudusaviBusy(null);
    await refreshLudusavi();
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? "Ludusavi installed" : `Install failed: ${res.error ?? "?"}`,
    });
  };

  const onLudusaviBackup = async () => {
    setLudusaviBusy("backup");
    const res = await ludusaviBackup(null);
    setLudusaviBusy(null);
    setLudusaviResult(res);
    toaster.toast({
      title: "DeckPiP",
      body: res.ok
        ? `Backup ok — ${res.summary?.games ?? "?"} games`
        : `Backup failed: rc=${res.rc ?? "?"}`,
    });
  };

  const onLudusaviRestore = async () => {
    setLudusaviBusy("restore");
    const res = await ludusaviRestore(null);
    setLudusaviBusy(null);
    setLudusaviResult(res);
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? "Restore ok" : `Restore failed: rc=${res.rc ?? "?"}`,
    });
  };

  const onLudusaviFind = async () => {
    setLudusaviBusy("find");
    const res = await ludusaviFind(null);
    setLudusaviBusy(null);
    setLudusaviResult(res);
  };

  const refreshRclone = async () => setRclone(await rcloneStatus());

  const onRcloneInstall = async () => {
    setRcloneBusy("install");
    const res = await rcloneInstall(false);
    setRcloneBusy(null);
    await refreshRclone();
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? "rclone installed" : `rclone install failed: ${res.error ?? "?"}`,
    });
  };

  const onRcloneListRemotes = async () => {
    setRcloneBusy("list");
    const res = await rcloneRemotes();
    setRcloneBusy(null);
    setRcloneRemoteList(res.remotes ?? []);
    if (!res.ok) {
      toaster.toast({
        title: "DeckPiP",
        body: `Couldn't read remotes — run "rclone config" first`,
      });
    }
  };

  const onCloudSync = async (direction: "up" | "down") => {
    if (!cloudRemote.trim()) {
      toaster.toast({ title: "DeckPiP", body: "Enter a remote name first" });
      return;
    }
    setRcloneBusy(direction);
    const fn = direction === "up" ? cloudSyncUp : cloudSyncDown;
    const res = await fn(cloudRemote.trim(), cloudPath.trim());
    setRcloneBusy(null);
    toaster.toast({
      title: "DeckPiP",
      body: res.ok ? `Sync ${direction} ok` : `Sync ${direction} failed: rc=${res.rc ?? "?"}`,
    });
  };

  const onMpris = async (bus: string, action: "PlayPause" | "Next" | "Previous") => {
    await mprisAction(bus, action);
    refreshMpris();
  };

  const onSaveAsDefault = async () => {
    const cur = store.get();
    const next: GameProfile = {
      app_id: running?.id ?? profile?.app_id ?? "discord_flatpak",
      audio_only: running?.audio_only ?? false,
      auto_launch: true,
      geom: cur.geom,
      opacity: cur.opacity,
    };
    await setProfile("default", next);
    toaster.toast({
      title: "DeckPiP",
      body: "Saved as default profile (used when a game has no profile of its own)",
    });
  };

  const onDiagnostics = async () => setDiag(await diagnostics());

  const onCheckUpdate = async () => {
    const info = await checkUpdate();
    setUpdateInfo(info);
    toaster.toast({ title: "DeckPiP", body: JSON.stringify(info).slice(0, 200) });
  };

  const onRunUpdate = async () => {
    const res = await runUpdate();
    toaster.toast({ title: "DeckPiP", body: JSON.stringify(res).slice(0, 200) });
  };

  const onSaveToken = async () => {
    await settingsSet("github_token", githubToken.trim());
    toaster.toast({ title: "DeckPiP", body: "GitHub token saved" });
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
              <ToggleField
                label="Touch mode"
                description="Larger drag bar and resize handle"
                checked={s.touchMode}
                onChange={(v) => store.set({ touchMode: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Lock layout"
                description="Disable drag and resize (anti-fumble)"
                checked={s.locked}
                onChange={(v) => store.set({ locked: v })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Pointer mode (trackpad-as-mouse)"
                description="Forward pointer events to the guest via xdotool. Enables clicking inside the PiP without a BT mouse."
                checked={s.inputMode === "pointer"}
                onChange={(v) => store.set({ inputMode: v ? "pointer" : "drag" })}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <SliderField
                label="Guest volume"
                description="Independent of system volume; via pactl on the guest's sink"
                value={guestVolume}
                min={0}
                max={150}
                step={5}
                onChange={onChangeGuestVolume}
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

            {currentAppid && (
              <>
                <PanelSectionRow>
                  <ButtonItem layout="below" onClick={() => onSaveProfile(false)}>
                    Save preset for {currentAppName ?? `appid ${currentAppid}`}
                  </ButtonItem>
                </PanelSectionRow>
                <PanelSectionRow>
                  <ToggleField
                    label="Auto-launch on this game"
                    description="Start DeckPiP automatically when this game starts"
                    checked={!!profile?.auto_launch}
                    onChange={(v) => onSaveProfile(v)}
                  />
                </PanelSectionRow>
                {profile && (
                  <PanelSectionRow>
                    <ButtonItem layout="below" onClick={onClearProfile}>
                      Clear profile
                    </ButtonItem>
                  </PanelSectionRow>
                )}
              </>
            )}
            <PanelSectionRow>
              <ButtonItem layout="below" onClick={onSaveAsDefault}>
                Save as default profile
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

      <PanelSection title="Save sync (Ludusavi)">
        <PanelSectionRow>
          <div style={{ fontSize: 11, color: "#bbb", padding: "4px 8px" }}>
            Works for Steam, Flatpak, and non-Steam / pirated copies
            (Ludusavi matches games by PCGamingWiki manifest, not by
            Steam metadata).
          </div>
        </PanelSectionRow>
        {!ludusavi?.installed && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={ludusaviBusy === "install"}
              onClick={onLudusaviInstall}
            >
              {ludusaviBusy === "install" ? "Downloading Ludusavi…" : "Install Ludusavi"}
            </ButtonItem>
          </PanelSectionRow>
        )}
        {ludusavi?.installed && (
          <>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={ludusaviBusy !== null}
                onClick={onLudusaviBackup}
              >
                {ludusaviBusy === "backup" ? "Backing up…" : "Backup all saves"}
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={ludusaviBusy !== null}
                onClick={onLudusaviRestore}
              >
                {ludusaviBusy === "restore" ? "Restoring…" : "Restore all saves"}
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={ludusaviBusy !== null}
                onClick={onLudusaviFind}
              >
                {ludusaviBusy === "find" ? "Scanning…" : "Find detectable games"}
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Auto-backup on game stop"
                description="When a game exits, run Ludusavi backup automatically"
                checked={autoBackup}
                onChange={async (v) => {
                  setAutoBackup(v);
                  await settingsSet("auto_backup_on_stop", v);
                }}
              />
            </PanelSectionRow>
          </>
        )}
        {ludusaviResult !== null && (
          <PanelSectionRow>
            <pre
              style={{
                fontSize: 10,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                background: "#111",
                color: "#ccc",
                padding: 6,
                borderRadius: 4,
                maxHeight: 200,
                overflow: "auto",
              }}
            >
              {JSON.stringify(ludusaviResult, null, 2).slice(0, 4000)}
            </pre>
          </PanelSectionRow>
        )}
      </PanelSection>

      <PanelSection title="Cloud sync (rclone)">
        <PanelSectionRow>
          <div style={{ fontSize: 11, color: "#bbb", padding: "4px 8px" }}>
            Push Ludusavi backups to Google Drive / Dropbox / OneDrive / S3 /
            SFTP / WebDAV — anything rclone supports. Configure remotes
            once in Desktop Mode with <b>rclone config</b>; we read{" "}
            {rclone?.config_file ?? "~/.config/rclone/rclone.conf"}.
          </div>
        </PanelSectionRow>
        {!rclone?.installed && (
          <PanelSectionRow>
            <ButtonItem
              layout="below"
              disabled={rcloneBusy === "install"}
              onClick={onRcloneInstall}
            >
              {rcloneBusy === "install" ? "Downloading rclone…" : "Install rclone"}
            </ButtonItem>
          </PanelSectionRow>
        )}
        {rclone?.installed && (
          <>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={rcloneBusy !== null}
                onClick={onRcloneListRemotes}
              >
                {rcloneBusy === "list"
                  ? "Reading remotes…"
                  : rcloneRemoteList.length > 0
                  ? `${rcloneRemoteList.length} remote${
                      rcloneRemoteList.length === 1 ? "" : "s"
                    } detected`
                  : "List configured remotes"}
              </ButtonItem>
            </PanelSectionRow>
            {rcloneRemoteList.length > 0 && (
              <PanelSectionRow>
                <div style={{ fontSize: 11, color: "#888", padding: "0 8px" }}>
                  Available: {rcloneRemoteList.join(", ")}
                </div>
              </PanelSectionRow>
            )}
            <PanelSectionRow>
              <TextField
                label="Remote name"
                value={cloudRemote}
                onChange={async (e) => {
                  const v = (e.target as HTMLInputElement).value;
                  setCloudRemote(v);
                  await settingsSet("cloud_remote", v);
                }}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <TextField
                label="Remote path"
                value={cloudPath}
                onChange={async (e) => {
                  const v = (e.target as HTMLInputElement).value;
                  setCloudPath(v);
                  await settingsSet("cloud_path", v);
                }}
              />
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={rcloneBusy !== null}
                onClick={() => onCloudSync("up")}
              >
                {rcloneBusy === "up" ? "Syncing up…" : "Sync backups to cloud"}
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ButtonItem
                layout="below"
                disabled={rcloneBusy !== null}
                onClick={() => onCloudSync("down")}
              >
                {rcloneBusy === "down" ? "Syncing down…" : "Pull backups from cloud"}
              </ButtonItem>
            </PanelSectionRow>
            <PanelSectionRow>
              <ToggleField
                label="Auto-sync after each backup"
                description="Pushes to the cloud remote whenever Ludusavi finishes a backup"
                checked={autoCloudSync}
                onChange={async (v) => {
                  setAutoCloudSync(v);
                  await settingsSet("auto_cloud_sync", v);
                }}
              />
            </PanelSectionRow>
          </>
        )}
      </PanelSection>

      <PanelSection title="Media">
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={refreshMpris}>
            {mprisPlayers.length === 0
              ? "Find media players"
              : `${mprisPlayers.length} media player${mprisPlayers.length === 1 ? "" : "s"}`}
          </ButtonItem>
        </PanelSectionRow>
        {mprisPlayers.map((p) => {
          const label = [p.title, p.artist].filter(Boolean).join(" — ") ||
            p.bus_name.replace(/^org\.mpris\.MediaPlayer2\./, "");
          return (
            <div key={p.bus_name}>
              <PanelSectionRow>
                <div style={{ fontSize: 11, color: "#bbb", padding: "4px 8px" }}>
                  {label}
                  {p.status ? ` (${p.status})` : ""}
                </div>
              </PanelSectionRow>
              <PanelSectionRow>
                <ButtonItem layout="below" onClick={() => onMpris(p.bus_name, "Previous")}>
                  ⏮ Prev
                </ButtonItem>
              </PanelSectionRow>
              <PanelSectionRow>
                <ButtonItem layout="below" onClick={() => onMpris(p.bus_name, "PlayPause")}>
                  {p.status === "Playing" ? "⏸ Pause" : "▶ Play"}
                </ButtonItem>
              </PanelSectionRow>
              <PanelSectionRow>
                <ButtonItem layout="below" onClick={() => onMpris(p.bus_name, "Next")}>
                  ⏭ Next
                </ButtonItem>
              </PanelSectionRow>
            </div>
          );
        })}
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
          <ButtonItem layout="below" onClick={() => onOpenWebPip()}>
            Open URL in PiP
          </ButtonItem>
        </PanelSectionRow>
        {bookmarks.length > 0 && (
          <>
            {bookmarks.map((bm) => (
              <PanelSectionRow key={bm.id}>
                <ButtonItem layout="below" onClick={() => onOpenWebPip(bm.url)}>
                  {bm.label}
                </ButtonItem>
                <ButtonItem layout="below" onClick={() => onRemoveBookmark(bm.id)}>
                  <FaTimes /> remove
                </ButtonItem>
              </PanelSectionRow>
            ))}
          </>
        )}
        <PanelSectionRow>
          <TextField
            label="New bookmark label"
            value={newBookmarkLabel}
            onChange={(e) => setNewBookmarkLabel((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="URL"
            value={newBookmarkUrl}
            onChange={(e) => setNewBookmarkUrl((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onAddBookmark}>
            Save bookmark
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

      <PanelSection title="Help">
        <PanelSectionRow>
          <div style={{ fontSize: 12, lineHeight: 1.5, color: "#bbb", padding: 4 }}>
            <b>F10</b> — toggle overlay visibility.
            <br />
            <b>F12 hold</b> — push-to-talk (unmute default microphone).
            <br />
            <b>Drag</b> the title bar to move; bottom-right corner to resize.
            Drop snaps to edges/center.
            <br />
            <b>Audio-only mode</b> keeps the guest alive without rendering the
            iframe — useful for voice chat.
            <br />
            <b>Save default profile</b> in the running panel to apply the same
            preset to any game that doesn't have its own.
            <br />
            Hotkeys only fire while Steam UI has keyboard focus.
          </div>
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
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={installingVendored}
            onClick={onInstallVendored}
          >
            {installingVendored
              ? "Vendoring noVNC + websockify…"
              : "Install vendored runtime"}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem
            layout="below"
            disabled={installingVendored}
            onClick={onInstallEverything}
          >
            {installingVendored
              ? "Installing everything…"
              : "Install everything (vendored + Ludusavi + rclone)"}
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onDiagnostics}>
            Show diagnostics
          </ButtonItem>
        </PanelSectionRow>
        {diag !== null && (
          <PanelSectionRow>
            <pre
              style={{
                fontSize: 10,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
                background: "#111",
                color: "#ccc",
                padding: 6,
                borderRadius: 4,
                maxHeight: 240,
                overflow: "auto",
              }}
            >
              {JSON.stringify(diag, null, 2)}
            </pre>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onCheckUpdate}>
            Check for update
          </ButtonItem>
        </PanelSectionRow>
        {updateInfo !== null && (
          <PanelSectionRow>
            <ButtonItem layout="below" onClick={onRunUpdate}>
              Run update
            </ButtonItem>
          </PanelSectionRow>
        )}
        <PanelSectionRow>
          <TextField
            label="GitHub PAT (for private repo updates)"
            value={githubToken}
            onChange={(e) => setGithubToken((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onSaveToken}>
            Save token
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          <TextField
            label="Toggle-visibility hotkey"
            value={s.hotkeyToggle}
            onChange={(e) => store.set({ hotkeyToggle: (e.target as HTMLInputElement).value })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Push-to-talk hotkey"
            value={s.hotkeyPtt}
            onChange={(e) => store.set({ hotkeyPtt: (e.target as HTMLInputElement).value })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Aggressive on low battery"
            description="Below 20 % on battery: drop opacity, kill mirror"
            checked={s.lowBattery}
            onChange={(v) => store.set({ lowBattery: v })}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ToggleField
            label="Mirror desktop notifications"
            description="Discord/Telegram DMs from Xvnc to Decky toaster"
            checked={notifMirror}
            onChange={onToggleNotifMirror}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onExport}>
            Export settings
          </ButtonItem>
        </PanelSectionRow>
        <PanelSectionRow>
          <TextField
            label="Paste JSON to import"
            value={importPayload}
            onChange={(e) => setImportPayload((e.target as HTMLInputElement).value)}
          />
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onImport}>
            Import settings (merge)
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
}
