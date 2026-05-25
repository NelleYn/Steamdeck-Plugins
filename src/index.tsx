import { definePlugin, routerHook, toaster } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaTv } from "react-icons/fa";

import { getProfile, listApps, pauseSession, ptt as pttCallable, resumeSession } from "./api";
import { Content, ROUTE, startFromUi } from "./panel";
import { onAppLifecycle } from "./steam";
import { ensureHydrated, store } from "./store";

const HOTKEY_TOGGLE = "F10";
const HOTKEY_PTT = "F12";
const PAUSE_DELAY_MS = 5000;

function installHotkey(): () => void {
  let pttHeld = false;
  const onDown = (e: KeyboardEvent) => {
    if (e.key === HOTKEY_TOGGLE) {
      e.preventDefault();
      store.set({ visible: !store.get().visible }, false);
    } else if (e.key === HOTKEY_PTT) {
      e.preventDefault();
      if (!pttHeld) {
        pttHeld = true;
        pttCallable("", "press").catch(() => {});
      }
    }
  };
  const onUp = (e: KeyboardEvent) => {
    if (e.key === HOTKEY_PTT && pttHeld) {
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

export default definePlugin(() => {
  const removeHotkey = installHotkey();
  const removeAutoLaunch = installAutoLaunch();
  const removePauseScheduler = installPauseScheduler();
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
    },
  };
});
