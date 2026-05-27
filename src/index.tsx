import { addEventListener, definePlugin, removeEventListener, routerHook, toaster } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaTv } from "react-icons/fa";

import {
  NotificationPayload,
  batteryState as batteryStateCallable,
  checkDeps,
  cloudSyncUp,
  getProfile,
  listApps,
  ludusaviBackup,
  pauseSession,
  ptt as pttCallable,
  resumeSession,
  settingsGet,
} from "./api";
import { Content, ROUTE, startFromUi } from "./panel";
import { onAppLifecycle, onScreenshot } from "./steam";
import { ensureHydrated, store, useStore } from "./store";

// Decky's toaster is imported lazily so tests don't need to mock it.
function toasterPort(): ((body: string) => void) | null {
  try {
    return (body) => toaster.toast({ title: "DeckPiP", body });
  } catch {
    return null;
  }
}

const PAUSE_DELAY_MS = 5000;

function installHotkey(): () => void {
  let pttHeld = false;
  const onDown = (e: KeyboardEvent) => {
    const { hotkeyToggle, hotkeyPtt } = store.get();
    if (e.key === hotkeyToggle) {
      e.preventDefault();
      store.set({ visible: !store.get().visible }, false);
    } else if (e.key === hotkeyPtt) {
      e.preventDefault();
      if (!pttHeld) {
        pttHeld = true;
        pttCallable("", "press").catch(() => {});
      }
    }
  };
  const onUp = (e: KeyboardEvent) => {
    if (e.key === store.get().hotkeyPtt && pttHeld) {
      e.preventDefault();
      pttHeld = false;
      pttCallable("", "release").catch(() => {});
    }
  };
  window.addEventListener("keydown", onDown);
  window.addEventListener("keyup", onUp);
  return () => {
    window.removeEventListener("keydown", onDown);
    window.removeEventListener("keyup", onUp);
  };
}

const BATTERY_POLL_MS = 60_000;
const LOW_BATTERY_THRESHOLD = 20;

/** Low-battery polling: drop opacity + mirror when on battery and <20 %. */
function installBatteryWatcher(): () => void {
  let timer: ReturnType<typeof setInterval> | null = null;
  let applied = false;
  const tick = async () => {
    if (!store.get().lowBattery) return;
    try {
      const bs = await batteryStateCallable();
      if (!bs.present) return;
      const trigger = bs.on_battery && (bs.percent ?? 100) <= LOW_BATTERY_THRESHOLD;
      if (trigger && !applied) {
        applied = true;
        store.set({ opacity: Math.min(store.get().opacity, 40), mirrorOn: false }, false);
        toasterPort()?.("Low battery — DeckPiP reduced overlay");
      } else if (!trigger && applied) {
        applied = false;
      }
    } catch {
      // ignore
    }
  };
  timer = setInterval(tick, BATTERY_POLL_MS);
  tick();
  return () => {
    if (timer) clearInterval(timer);
  };
}

/** SIGSTOP Xvnc+guest after the overlay has been hidden for 5 s; SIGCONT on
 *  show. Drops idle CPU cost to zero while the user can't see the PiP. */
function installPauseScheduler(): () => void {
  let pauseTimer: ReturnType<typeof setTimeout> | null = null;
  let isPaused = false;
  let cancelled = false;
  const clear = () => {
    if (pauseTimer) {
      clearTimeout(pauseTimer);
      pauseTimer = null;
    }
  };
  const unsubscribe = store.subscribe(() => {
    if (cancelled) return;
    const s = store.get();
    if (!s.url) {
      clear();
      isPaused = false;
      return;
    }
    if (s.visible) {
      clear();
      if (isPaused) {
        isPaused = false;
        resumeSession().catch(() => {});
      }
    } else if (!pauseTimer && !isPaused) {
      pauseTimer = setTimeout(() => {
        pauseTimer = null;
        if (cancelled || store.get().visible) return;
        isPaused = true;
        pauseSession().catch(() => {});
      }, PAUSE_DELAY_MS);
    }
  });
  return () => {
    cancelled = true;
    clear();
    unsubscribe();
  };
}

/** Look up the profile for an appid, falling back to a "default" profile. */
async function resolveProfile(appid: number) {
  const direct = await getProfile(String(appid));
  if (direct) return direct;
  return await getProfile("default");
}

function installAutoLaunch(): () => void {
  return onAppLifecycle(async ({ appid, running }) => {
    const w = window as unknown as { __DECKPIP_CURRENT_APPID__?: number };
    if (running) {
      w.__DECKPIP_CURRENT_APPID__ = appid;
    } else if (w.__DECKPIP_CURRENT_APPID__ === appid) {
      delete w.__DECKPIP_CURRENT_APPID__;
    }

    if (!running) return;
    try {
      const profile = await resolveProfile(appid);
      if (!profile?.auto_launch) return;
      const apps = await listApps();
      const target = apps.find((a) => a.id === profile.app_id);
      if (!target) {
        toaster.toast({
          title: "DeckPiP",
          body: `Auto-launch skipped: app "${profile.app_id}" not in registry`,
        });
        return;
      }
      if (profile.geom) store.set({ geom: profile.geom }, false);
      if (typeof profile.opacity === "number") store.set({ opacity: profile.opacity }, false);
      await startFromUi(target, profile.audio_only ?? false);
    } catch {
      // ignore
    }
  });
}

function installNotificationListener(): () => void {
  const handler = (payload: NotificationPayload) => {
    if (!payload?.app) return;
    const body = [payload.summary, payload.body].filter(Boolean).join(" — ");
    try {
      toaster.toast({ title: `${payload.app}`, body: body.slice(0, 200) });
    } catch {
      // ignore
    }
  };
  try {
    addEventListener<[NotificationPayload]>("deckpip_notification", handler);
  } catch {
    // ignore
  }
  return () => {
    try {
      removeEventListener("deckpip_notification", handler);
    } catch {
      // ignore
    }
  };
}

/** Auto-backup saves via Ludusavi when a game stops, optionally followed
 *  by an rclone sync. Best-effort; errors land in toasts. */
function installAutoBackup(): () => void {
  return onAppLifecycle(async ({ running }) => {
    if (running) return;
    try {
      const enabled = await settingsGet("auto_backup_on_stop", false);
      if (!enabled) return;
      const res = await ludusaviBackup(null);
      if (res.ok) {
        toaster.toast({
          title: "DeckPiP",
          body: `Auto-backup ok — ${res.summary?.games ?? "?"} games`,
        });
      } else {
        toaster.toast({
          title: "DeckPiP",
          body: `Auto-backup failed (rc=${res.rc ?? "?"})`,
        });
        return;
      }
      const autoCloud = await settingsGet("auto_cloud_sync", false);
      if (!autoCloud) return;
      const remote = (await settingsGet("cloud_remote", "")) as string;
      const path = ((await settingsGet("cloud_path", "DeckPiP/backups")) as string) ||
        "DeckPiP/backups";
      if (!remote) {
        toaster.toast({
          title: "DeckPiP",
          body: "Auto-cloud-sync skipped: no remote configured",
        });
        return;
      }
      const sync = await cloudSyncUp(remote, path);
      toaster.toast({
        title: "DeckPiP",
        body: sync.ok ? "Cloud sync up ok" : `Cloud sync failed (rc=${sync.rc ?? "?"})`,
      });
    } catch {
      // ignore
    }
  });
}

/** On Steam screenshot, copy path to clipboard so the user can paste it
 *  into the active PiP guest. */
function installScreenshotHook(): () => void {
  return onScreenshot(async ({ path }) => {
    if (!store.get().url || !path) return;
    try {
      await navigator.clipboard?.writeText?.(path);
      toaster.toast({
        title: "DeckPiP",
        body: "Screenshot path copied — paste into your PiP guest",
      });
    } catch {
      toaster.toast({
        title: "DeckPiP",
        body: `Screenshot: ${path.slice(0, 120)}`,
      });
    }
  });
}

const DEPS_POLL_MS = 60_000;

/** Required pacman deps survival check.
 *
 *  SteamOS resets its read-only root on every system update, which silently
 *  uninstalls tigervnc and friends. We poll once a minute and surface the
 *  result in two places:
 *    1. A red marker in the plugin title view (always visible in QA).
 *    2. A "Setup required" callout at the top of the panel content with a
 *       one-tap reinstall button.
 *  Plus a single toast on first detection so the user gets nudged. */
function installDepsHealthCheck(): () => void {
  let prevHealthy = true;
  let toldUser = false;
  const tick = async () => {
    try {
      const d = await checkDeps();
      const missing: string[] = Object.entries(d)
        .filter(([k, ok]) => !k.startsWith("_optional_") && !ok)
        .map(([k]) => k);
      const healthy = missing.length === 0;
      store.set({ depsHealthy: healthy, depsMissing: missing }, false);
      if (!healthy && (prevHealthy || !toldUser)) {
        toldUser = true;
        try {
          toaster.toast({
            title: "DeckPiP",
            body:
              "Setup required — pacman deps missing (likely after a SteamOS " +
              "update). Open DeckPiP -> Setup required -> Reinstall.",
          });
        } catch {
          // ignore
        }
      } else if (healthy && !prevHealthy) {
        toldUser = false;
      }
      prevHealthy = healthy;
    } catch {
      // ignore
    }
  };
  tick();
  const interval = setInterval(tick, DEPS_POLL_MS);
  return () => clearInterval(interval);
}

function TitleView() {
  const s = useStore();
  return (
    <div className={staticClasses.Title}>
      DeckPiP
      {!s.depsHealthy && (
        <span title={`Missing: ${s.depsMissing.join(", ")}`} style={{ marginLeft: 6 }}>
          🔴
        </span>
      )}
    </div>
  );
}

export default definePlugin(() => {
  const removeHotkey = installHotkey();
  const removeAutoLaunch = installAutoLaunch();
  const removePauseScheduler = installPauseScheduler();
  const removeBatteryWatcher = installBatteryWatcher();
  const removeNotifListener = installNotificationListener();
  const removeScreenshotHook = installScreenshotHook();
  const removeAutoBackup = installAutoBackup();
  const removeHealthCheck = installDepsHealthCheck();
  ensureHydrated();
  return {
    name: "DeckPiP",
    titleView: <TitleView />,
    content: <Content />,
    icon: <FaTv />,
    onDismount() {
      try {
        routerHook.removeRoute(ROUTE);
      } catch {
        // ignore
      }
      removeHotkey();
      removeAutoLaunch();
      removePauseScheduler();
      removeBatteryWatcher();
      removeNotifListener();
      removeScreenshotHook();
      removeAutoBackup();
      removeHealthCheck();
    },
  };
});
