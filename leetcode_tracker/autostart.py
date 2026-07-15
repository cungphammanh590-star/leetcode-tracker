"""macOS LaunchAgent 自启 manage。"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from leetcode_tracker.config import load_config, save_config

LABEL = "com.leetcode-tracker.serve"


def _agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def plist_path() -> Path:
    return _agents_dir() / f"{LABEL}.plist"


def _leetcode_tracker_bin() -> str:
    which = shutil.which("leetcode-tracker")
    if which:
        return which
    candidate = Path(sys.executable).with_name("leetcode-tracker")
    if candidate.exists():
        return str(candidate)
    return "leetcode-tracker"


def install_autostart() -> Path:
    cfg = load_config()
    bin_path = _leetcode_tracker_bin()
    program_args = [bin_path, "serve", "--host", str(cfg["host"]), "--port", str(cfg["port"])]
    plist = {
        "Label": LABEL,
        "ProgramArguments": program_args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(Path.home() / "Library" / "Logs" / "leetcode-tracker.out.log"),
        "StandardErrorPath": str(Path.home() / "Library" / "Logs" / "leetcode-tracker.err.log"),
    }
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    Path.home().joinpath("Library", "Logs").mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        plistlib.dump(plist, fh)

    subprocess.run(["launchctl", "unload", str(path)], check=False, capture_output=True)
    result = subprocess.run(
        ["launchctl", "load", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # macOS newer may prefer bootstrap; keep file even if load fails
        pass

    cfg["autostart"] = True
    save_config(cfg)
    return path


def uninstall_autostart() -> Path | None:
    path = plist_path()
    existed = path.exists()
    if existed:
        subprocess.run(["launchctl", "unload", str(path)], check=False, capture_output=True)
        path.unlink(missing_ok=True)
    cfg = load_config()
    cfg["autostart"] = False
    save_config(cfg)
    return path if existed else None
