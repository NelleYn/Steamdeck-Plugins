/**
 * Defensive shims around the Steam Deck's SteamClient APIs.
 *
 * Decky exposes `(window as any).SteamClient` and `(window as any).appStore`
 * — but the surface varies by SteamUI version, so every call is wrapped in
 * a try/catch and falls back to "unknown" rather than crashing the plugin.
 */

declare const window: Window & {
  SteamClient?: {
    GameSessions?: {
      RegisterForAppLifetimeNotifications?: (
        cb: (data: { unAppID: number; bRunning: boolean }) => void,
      ) => { unregister: () => void };
      RegisterForScreenshotNotification?: (
        cb: (data: {
          unAppID: number;
          hScreenshot?: number;
          strOperation?: string;
          details?: { strUrl?: string; strLocalFilename?: string };
        }) => void,
      ) => { unregister: () => void };
    };
    Apps?: {
      RegisterForGameActionStart?: (
        cb: (actionType: number, appid: string) => void,
      ) => { unregister: () => void };
    };
  };
  appStore?: {
    GetAppOverviewByAppID?: (appid: number) => { display_name?: string; appid?: number } | null;
  };
};

export type GameLifetimeEvent = { appid: number; running: boolean };
export type ScreenshotEvent = {
  appid: number;
  path?: string;
  url?: string;
  operation?: string;
};

export function getAppName(appid: number): string | null {
  try {
    const ov = window.appStore?.GetAppOverviewByAppID?.(appid);
    return ov?.display_name ?? null;
  } catch {
    return null;
  }
}

export function onAppLifecycle(
  cb: (event: GameLifetimeEvent) => void,
): () => void {
  try {
    const reg = window.SteamClient?.GameSessions?.RegisterForAppLifetimeNotifications?.((data) => {
      cb({ appid: data.unAppID, running: data.bRunning });
    });
    return () => {
      try {
        reg?.unregister?.();
      } catch {
        // ignore
      }
    };
  } catch {
    return () => {};
  }
}

export function onScreenshot(cb: (event: ScreenshotEvent) => void): () => void {
  try {
    const reg = window.SteamClient?.GameSessions?.RegisterForScreenshotNotification?.((data) => {
      if (data.strOperation && data.strOperation !== "written") return;
      cb({
        appid: data.unAppID,
        path: data.details?.strLocalFilename,
        url: data.details?.strUrl,
        operation: data.strOperation,
      });
    });
    return () => {
      try {
        reg?.unregister?.();
      } catch {
        // ignore
      }
    };
  } catch {
    return () => {};
  }
}
