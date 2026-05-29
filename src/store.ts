import { useSyncExternalStore } from "react";

import { settingsGet, settingsSet } from "./api";
import {
  createStore,
  Persisted,
  SETTINGS_KEY,
  State,
  Store,
} from "./store-core";

export { DEFAULT_STATE, SETTINGS_KEY } from "./store-core";
export type { Persisted, State, Store };

export const store: Store = createStore((p) => {
  settingsSet(SETTINGS_KEY, p).catch(() => {});
});

let hydrated = false;
export const ensureHydrated = async (): Promise<void> => {
  if (hydrated) return;
  hydrated = true;
  const p = (await settingsGet(SETTINGS_KEY, null).catch(
    () => null,
  )) as Partial<Persisted> | null;
  if (p) store.hydrate(p);
};

export const useStore = (): State =>
  useSyncExternalStore(store.subscribe, store.get, store.get);
