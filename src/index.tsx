import {
  ButtonItem,
  PanelSection,
  PanelSectionRow,
  Navigation,
  staticClasses,
} from "@decky/ui";
import { callable, definePlugin, routerHook, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { FaTv } from "react-icons/fa";

type AppEntry = { id: string; label: string };
type StartResult = { ok: boolean; url?: string; error?: string };

const listApps = callable<[], AppEntry[]>("list_apps");
const startPip = callable<[app_id: string], StartResult>("start_pip");
const stopPip = callable<[], { ok: boolean }>("stop_pip");

const ROUTE = "/deckpip/view";

function PipView({ url }: { url: string }) {
  return (
    <iframe
      src={url}
      style={{
        position: "absolute",
        inset: 0,
        width: "100%",
        height: "100%",
        border: "none",
        background: "#000",
      }}
    />
  );
}

function Content() {
  const [apps, setApps] = useState<AppEntry[]>([]);
  const [running, setRunning] = useState<string | null>(null);

  useEffect(() => {
    listApps().then(setApps);
  }, []);

  const onStart = async (appId: string) => {
    const res = await startPip(appId);
    if (!res.ok || !res.url) {
      toaster.toast({ title: "DeckPiP", body: `Start failed: ${res.error ?? "unknown"}` });
      return;
    }
    routerHook.addRoute(ROUTE, () => <PipView url={res.url!} />, { exact: true });
    setRunning(appId);
    Navigation.Navigate(ROUTE);
    Navigation.CloseSideMenus();
  };

  const onStop = async () => {
    await stopPip();
    routerHook.removeRoute(ROUTE);
    setRunning(null);
  };

  return (
    <PanelSection title="DeckPiP">
      {running ? (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onStop}>
            Stop ({running})
          </ButtonItem>
        </PanelSectionRow>
      ) : (
        apps.map((app) => (
          <PanelSectionRow key={app.id}>
            <ButtonItem layout="below" onClick={() => onStart(app.id)}>
              {app.label}
            </ButtonItem>
          </PanelSectionRow>
        ))
      )}
    </PanelSection>
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
      } catch {
        // route may not be registered
      }
    },
  };
});
