from __future__ import annotations

import subprocess

import pytest

import stock_radar.notification.desktop as desktop_module
from stock_radar.notification.desktop import DesktopNotificationError, send_desktop_notification


class FakeCompletedProcess:
    def __init__(self, returncode=0, stderr=""):
        self.returncode = returncode
        self.stderr = stderr


def test_sends_via_osascript_on_macos(monkeypatch):
    monkeypatch.setattr(desktop_module.platform, "system", lambda: "Darwin")
    captured = {}

    def fake_run(args, capture_output, text):
        captured["args"] = args
        return FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(desktop_module.subprocess, "run", fake_run)

    send_desktop_notification("件名", "本文")

    assert captured["args"][0] == "osascript"
    assert "display notification" in captured["args"][2]
    assert "本文" in captured["args"][2]
    assert "件名" in captured["args"][2]


def test_escapes_double_quotes_and_backslashes(monkeypatch):
    monkeypatch.setattr(desktop_module.platform, "system", lambda: "Darwin")
    captured = {}

    def fake_run(args, capture_output, text):
        captured["script"] = args[2]
        return FakeCompletedProcess(returncode=0)

    monkeypatch.setattr(desktop_module.subprocess, "run", fake_run)

    send_desktop_notification('タイトル"引用"', "バック\\スラッシュ")

    assert '\\"引用\\"' in captured["script"]
    assert "\\\\スラッシュ" in captured["script"]


def test_raises_on_osascript_failure(monkeypatch):
    monkeypatch.setattr(desktop_module.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        desktop_module.subprocess, "run",
        lambda args, capture_output, text: FakeCompletedProcess(returncode=1, stderr="boom"),
    )
    with pytest.raises(DesktopNotificationError, match="boom"):
        send_desktop_notification("件名", "本文")


def test_raises_on_unsupported_platform(monkeypatch):
    monkeypatch.setattr(desktop_module.platform, "system", lambda: "Linux")
    with pytest.raises(DesktopNotificationError, match="Linux"):
        send_desktop_notification("件名", "本文")
