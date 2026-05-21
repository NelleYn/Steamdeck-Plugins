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
export const settingsSet = callable<[key: string, value: unknown], SimpleResult>("settings_set");
export const addCustomApp = callable<
  [id: string, label: string, command: string],
  SimpleResult
>("add_custom_app");
export const removeCustomApp = callable<[id: string], SimpleResult>("remove_custom_app");
export const startMirror = callable<[], SimpleResult>("start_game_mirror");
export const stopMirror = callable<[], SimpleResult>("stop_game_mirror");
