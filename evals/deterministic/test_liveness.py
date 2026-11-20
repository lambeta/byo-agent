"""A pid is alive only when the operating system says so."""

from __future__ import annotations

import os
import subprocess

from byo.ops.liveness import alive


def test_the_current_process_is_alive():
    assert alive(os.getpid()) is True


def test_an_exited_process_is_not_alive():
    process = subprocess.Popen(["true"])
    process.wait()
    assert alive(process.pid) is False


def test_missing_or_nonsense_pids_are_not_alive():
    for pid in (None, 0, -1, "", "abc"):
        assert alive(pid) is False


def test_permission_denied_means_alive(monkeypatch):
    import byo.ops.liveness as module

    def denied(pid, signal):
        raise PermissionError("not allowed")

    monkeypatch.setattr(module.os, "kill", denied)
    assert alive(1234) is True


def test_a_generic_os_error_means_not_alive(monkeypatch):
    import byo.ops.liveness as module

    def invalid(pid, signal):
        raise OSError("invalid argument")

    monkeypatch.setattr(module.os, "kill", invalid)
    assert alive(1234) is False
