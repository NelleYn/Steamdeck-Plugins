import { Geom, PRESETS } from "./presets";

export type Persisted = {
  geom: Geom;
  opacity: number;
  clickThrough: boolean;
  touchMode: boolean;
  locked: boolean;
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
  touchMode: false,
  locked: false,
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

function isValidGeom(g: unknown): g is Geom {
  return (
    typeof g === "object" &&
    g !== null &&
    typeof (g as Geom).x === "number" &&
    typeof (g as Geom).y === "number" &&
    typeof (g as Geom).w === "number" &&
    typeof (g as Geom).h === "number"
  );
}

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
        touchMode: state.touchMode,
        locked: state.locked,
      });
    }
  };

  const hydrate: Store["hydrate"] = (p) => {
    state = {
      ...state,
      geom: isValidGeom(p.geom) ? p.geom! : state.geom,
      opacity: typeof p.opacity === "number" ? p.opacity : state.opacity,
      clickThrough: typeof p.clickThrough === "boolean" ? p.clickThrough : state.clickThrough,
      touchMode: typeof p.touchMode === "boolean" ? p.touchMode : state.touchMode,
      locked: typeof p.locked === "boolean" ? p.locked : state.locked,
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
