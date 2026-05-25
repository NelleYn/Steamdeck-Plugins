import { callable } from "@decky/api";

export type AppEntry = { id: string; label: string; command?: string[] };
export type StartResult = { ok: boolean; url?: string; audio_only?: boolean; error?: string };
export type DepStatus = Record<string, boolean>;
export type InstallResult = {
  ok: boolean;
  rc?: number;
  stdout?: string;
  stderr?: string;
  error?: string;
};
export type SimpleResult = { ok: boolean; error?: string };

export const listApps = callable<[], AppEntry[]>("list_apps");
export const checkDeps = callable<[], DepStatus>("check_dependencies");
export const installDeps = callable<[], InstallResult>("install_dependencies");
export const startPip = callable<[app_id: string, audio_only: boolean], StartResult>("start_pip");
export const stopPip = callable<[], SimpleResult>("stop_pip");
export const settingsGet = callable<[key: string, dflt: unknown], unknown>("settings_get");
export const settingsSet = callable<[key: string, value: unknown], SimpleResult>("settings_set");export const addCustomApp = callable<
  [id: string, label: string, command: string],
  SimpleResult
>("add_custom_app");
export const removeCustomApp = callable<[id: string], SimpleResult>("remove_custom_app");
export const startMirror = callable<[], SimpleResult>("start_game_mirror");
export const stopMirror = callable<[], SimpleResult>("stop_game_mirror");

export const pauseSession = callable<[], SimpleResult>("pause_session");
export const resumeSession = callable<[], SimpleResult>("resume_session");
export const setGuestVolume = callable<[percent: number], SimpleResult & { count?: number }>(
  "set_guest_volume",
);

export type BatteryState = {
  present: boolean;
  percent?: number;
  status?: string;
  charging?: boolean;
  on_battery?: boolean;
};
export const batteryState = callable<[], BatteryState>("battery_state");

export const exportSettings = callable<
  [],
  { ok: boolean; data?: Record<string, unknown> }
>("export_settings");
export const importSettings = callable<
  [payload: Record<string, unknown>, merge: boolean],
  SimpleResult
>("import_settings");

export type VendorStatus = { novnc: string; websockify: string; root: string };
export const vendorStatus = callable<[], VendorStatus>("vendor_status");
export const installVendored = callable<[force: boolean], Record<string, unknown>>(
  "install_vendored",
);

// ----- per-game profiles ---------------------------------------------------

export type GameProfile = {
  app_id: string;
  audio_only?: boolean;
  auto_launch?: boolean;
  geom?: { x: number; y: number; w: number; h: number } | null;
  opacity?: number | null;
};

export const listProfiles = callable<[], Record<string, GameProfile>>("list_profiles");
export const getProfile = callable<[appid: string], GameProfile | null>("get_profile");
export const setProfile = callable<[appid: string, profile: GameProfile], SimpleResult>(
  "set_profile",
);
export const removeProfile = callable<[appid: string], SimpleResult>("remove_profile");

// ----- bookmarks -----------------------------------------------------------

export type Bookmark = { id: string; label: string; url: string };

export const listBookmarks = callable<[], Bookmark[]>("list_bookmarks");
export const addBookmark = callable<[id: string, label: string, url: string], SimpleResult>(
  "add_bookmark",
);
export const removeBookmark = callable<[id: string], SimpleResult>("remove_bookmark");

// ----- diagnostics + PTT + updater -----------------------------------------

export type Diagnostics = Record<string, unknown>;

export const diagnostics = callable<[], Diagnostics>("diagnostics");
export const ptt = callable<[key_combo: string, action: "press" | "release" | "key"], SimpleResult>(
  "ptt",
);
export const checkUpdate = callable<[], Record<string, unknown>>("check_update");
export const runUpdate = callable<[], Record<string, unknown>>("run_update");
