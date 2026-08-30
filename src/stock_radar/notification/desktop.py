"""Desktop notification (spec §5: "デスクトップ通知等、ローカルで完結する
手段（外部有料サービス不要）").

macOS only for now, via the built-in `osascript` command — the user's real
test machine is a Mac, and this needs zero extra dependencies (no pyobjc/
plyer). Extend _send for other platforms if this is later run on the
spec's originally-assumed Windows target (e.g. PowerShell's
New-BurntToastNotification, or a library like plyer/win10toast).
"""

from __future__ import annotations

import platform
import subprocess


class DesktopNotificationError(RuntimeError):
    pass


def send_desktop_notification(title: str, message: str) -> None:
    system = platform.system()
    if system == "Darwin":
        _send_macos(title, message)
    else:
        raise DesktopNotificationError(
            f"Desktop notifications are not implemented for {system!r} yet "
            "(only macOS, via osascript, is supported currently)."
        )


def _send_macos(title: str, message: str) -> None:
    script = (
        f'display notification "{_escape_applescript(message)}" '
        f'with title "{_escape_applescript(title)}"'
    )
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        raise DesktopNotificationError(f"osascript failed: {result.stderr.strip()}")


def _escape_applescript(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
