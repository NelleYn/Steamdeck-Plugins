import { definePlugin, routerHook, toaster } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaTv } from "react-icons/fa";

import { getProfile, ptt as pttCallable, listApps } from "./api";
import { Content, ROUTE, startFromUi } from "./panel";
import { onAppLifecycle } from "./steam";
import { ensureHydrated, store } from "./store";

const PTT_KEY = "F12";
const PTT_COMBO = "ctrl+shift+m"; // Discord PTT default

function installHotkey(): () => void {
  let pttHeld = false;
  const onDown = (e: KeyboardEvent) => {
    if (e.key === "F10") {
      e.preventDefault();
      store.set({ visible: !store.get().visible }, false);
    } else if (e.key === PTT_KEY) {
      e.preventDefault();
      if (!pttHeld) {
        pttHeld = true;
        pttCallable(PTT_COMBO, "press").catch(() => {});
      }
    }
  };
  const onUp = (e: KeyboardEvent) => {
    if (e.key === PTT_KEY && pttHeld) {
      e.preventDefault();
      pttHeld = false;
      pttCallable(PTT_COMBO, "release").catch(() => {});
    }
  };
  window.addEventListener("keydown", onDown);
  window.addEventListener("keyup", onUp);
  return () => {
    window.removeEventListener("keydown", onDown);
    window.removeEventListener("keyup", onUp);
  };
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
      const profile = await getProfile(String(appid));
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
    },
  };
});
