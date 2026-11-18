"""The Make targets keep their contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def dry_run(target: str) -> str:
    return subprocess.run(
        ["make", "-n", target], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


def test_eval_and_gate_run_the_same_suite():
    for target in ("eval", "gate"):
        out = dry_run(target)
        assert "evals/deterministic" in out
        assert "pytest" in out


def test_lint_covers_the_package_and_the_evals():
    out = dry_run("lint")
    assert "ruff check" in out
    assert "byo/" in out and "evals/" in out


def test_run_targets_use_the_module_entrypoint():
    assert "-m byo" in dry_run("run")
    assert "-m byo dashboard" in dry_run("dashboard")
    assert "-m byo trajectory" in dry_run("trajectory")
