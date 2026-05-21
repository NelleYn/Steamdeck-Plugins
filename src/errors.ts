export function friendlyError(err: string | undefined): string {
  if (!err) return "Unknown error";
  if (err === "already_running") return "Session is already running";
  if (err === "no_session") return "Start a PiP session first";
  if (err === "already_mirroring") return "Game mirror already running";
  if (err === "no_gamescope_pw_node")
    return "Gamescope PipeWire node not found (game not running?)";
  if (err === "unknown_app") return "App not in registry";
  if (err === "empty_command") return "Command is empty";
  if (err.startsWith("missing_dependency:")) {
    const dep = err.split(":", 2)[1] ?? "?";
    if (dep === "Xvnc" || dep === "vncpasswd")
      return "TigerVNC missing — tap Install dependencies";
    if (dep === "novnc") return "noVNC missing — tap Install dependencies";
    if (dep === "websockify") return "websockify missing — tap Install dependencies";
    if (dep === "gstreamer")
      return "gstreamer missing — sudo pacman -S gst-plugins-good gst-plugin-pipewire";
    return `Missing: ${dep}`;
  }
  if (err.startsWith("parse_error:")) {
    return `Could not parse command: ${err.slice("parse_error:".length)}`;
  }
  return err;
}
