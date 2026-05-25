import { describe, expect, it } from "vitest";

import { friendlyError } from "../errors";

describe("friendlyError", () => {
  it("falls back when err is undefined", () => {
    expect(friendlyError(undefined)).toBe("Unknown error");
  });

  it("maps simple errors", () => {
    expect(friendlyError("already_running")).toMatch(/already running/);
    expect(friendlyError("no_session")).toMatch(/PiP session first/);
    expect(friendlyError("no_gamescope_pw_node")).toMatch(/Gamescope PipeWire/);
    expect(friendlyError("unknown_app")).toMatch(/not in registry/);
    expect(friendlyError("empty_command")).toMatch(/empty/);
  });

  it("recognises specific missing dependencies", () => {
    expect(friendlyError("missing_dependency:Xvnc")).toMatch(/TigerVNC/);
    expect(friendlyError("missing_dependency:vncpasswd")).toMatch(/TigerVNC/);
    expect(friendlyError("missing_dependency:novnc")).toMatch(/noVNC/);
    expect(friendlyError("missing_dependency:websockify")).toMatch(/websockify/);
    expect(friendlyError("missing_dependency:pactl")).toMatch(/PTT/);
    expect(friendlyError("missing_dependency:gstreamer")).toMatch(/GameMirror/);
  });

  it("formats pactl PTT failures", () => {
    expect(friendlyError("pactl_rc:1:Connection refused")).toBe(
      "PTT failed: 1:Connection refused",
    );
  });

  it("falls back to dep name for unknown missing dependency", () => {
    expect(friendlyError("missing_dependency:weird-dep")).toBe("Missing: weird-dep");
  });

  it("formats parse errors", () => {
    expect(friendlyError("parse_error:No closing quotation")).toBe(
      "Could not parse command: No closing quotation",
    );
  });

  it("passes unknown errors through verbatim", () => {
    expect(friendlyError("totally unexpected")).toBe("totally unexpected");
  });
});
