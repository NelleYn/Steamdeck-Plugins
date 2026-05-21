import { Geom, PRESETS } from "./presets";

export type Persisted = {
  geom: Geom;
  opacity: number;
  clickThrough: boolean;
};

export type State = Persisted & {
  url: string;
  visible: boolean;
  mirrorOn: boolean;
};

export const SETTINGS_KEY = "ui_state_v1";

export const DEFAULT_STATE: State = {
  url: "",
  geom: PRESETS["small-br"],
  opacity: 95,
  clickThrough: false,
  visible: true,
  mirrorOn: false,
};

export type Store = {
  get: () => State;
  set: (patch: Partial<State>, persist?: boolean) => void;
  subscribe: (cb: () => void) => () => void;
  hydrate: (p: Partial<Persisted>) => void;
};

type PersistFn = (p: Persisted) => void;

export function createStore(persistFn: PersistFn = () => {}): Store {
  let state: State = { ...DEFAULT_STATE };
  const listeners = new Set<() => void>();

  const set: Store["set"] = (patch, persist = true) => {
    state = { ...state, ...patch };
    listeners.forEach((l) => l());
    if (persist) {
      persistFn({
        geom: state.geom,
        opacity: state.opacity,
        clickThrough: state.clickThrough,
      });
    }
  };

  const hydrate: Store["hydrate"] = (p) => {
    state = {
      ...state,
      geom: p.geom ?? state.geom,
      opacity: typeof p.opacity === "number" ? p.opacity : state.opacity,
      clickThrough: typeof p.clickThrough === "boolean" ? p.clickThrough : state.clickThrough,
    };
    listeners.forEach((l) => l());
  };

  const subscribe: Store["subscribe"] = (cb) => {
    listeners.add(cb);
    return () => {
      listeners.delete(cb);
    };
  };

  return { get: () => state, set, subscribe, hydrate };
}
