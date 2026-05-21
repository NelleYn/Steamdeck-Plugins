import { definePlugin, routerHook } from "@decky/api";
import { staticClasses } from "@decky/ui";
import { FaTv } from "react-icons/fa";

import { Content, ROUTE } from "./panel";
import { ensureHydrated, store } from "./store";

function installHotkey(): () => void {
  const handler = (e: KeyboardEvent) => {
    if (e.key === "F10") {
      e.preventDefault();
      store.set({ visible: !store.get().visible }, false);
    }
  };
  window.addEventListener("keydown", handler);
  return () => window.removeEventListener("keydown", handler);
}

export default definePlugin(() => {
  const removeHotkey = installHotkey();
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
    },
  };
});
