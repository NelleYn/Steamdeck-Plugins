import { addEventListener, definePlugin, removeEventListener, routerHook, toaster } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaTv } from "react-icons/fa";

import {
  NotificationPayload,
  batteryState as batteryStateCallable,
  getProfile,
  listApps,
  pauseSession,
  ptt as pttCallable,
  resumeSession,
} from "./api";
import { Content, ROUTE, startFromUi } from "./panel";
import { onAppLifecycle, onScreenshot } from "./steam";
import { ensureHydrated, store } from "./store";

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

/** When the user enables low-battery mode, poll once a minute and apply
 *  a more conservative overlay (lower opacity, mirror off) once we drop
 *  below 20 % on battery. */
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


/**
 * SIGSTOP the Xvnc + guest process group when the overlay has been hidden
 * for more than PAUSE_DELAY_MS. Resume immediately on show. The hidden cost
 * (~5–15 % CPU on a running game depending on guest) drops to zero while
 * the user can't see the PiP anyway.
 */
function installPauseScheduler(): () => void {
  let pauseTimer: ReturnType<typeof setTimeout> | null = null;
  let isPaused = false;
  const clear = () => {
    if (pauseTimer) {
      clearTimeout(pauseTimer);
      pauseTimer = null;
    }
  };
  return store.subscribe(() => {
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
        if (!store.get().visible) {
          isPaused = true;
          pauseSession().catch(() => {});
        }
      }, PAUSE_DELAY_MS);
    }
  });
}

/** Look up the profile for an appid, falling back to a "default" profile
 *  the user can save without picking a specific game. */
async function resolveProfile(appid: number) {
  const direct = await getProfile(String(appid));
  if (direct) return direct;
  return await getProfile("default");
}

function installAutoLaunch(): () => void {
  return onAppLifecycle(async ({ appid, running }) => {
    // Expose to the panel so the running session can show "Save profile for <game>".
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
    // event API may not be present; no-op
  }
  return () => {
    try {
      removeEventListener("deckpip_notification", handler);
    } catch {
      // ignore
    }
  };
}

/** When Steam captures a screenshot, offer to share it via the active
 *  PiP guest (copy the path to clipboard so the user can paste it into
 *  Discord/Telegram). No-op without an active session. */
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

export default definePlugin(() => {
  const removeHotkey = installHotkey();
  const removeAutoLaunch = installAutoLaunch();
  const removePauseScheduler = installPauseScheduler();
  const removeBatteryWatcher = installBatteryWatcher();
  const removeNotifListener = installNotificationListener();
  const removeScreenshotHook = installScreenshotHook();
  ensureHydrated();
  return {
    name: "DeckPiP",
    titleView: <div className={staticClasses.Title}>DeckPiP</div>,
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
    },
  };
});
