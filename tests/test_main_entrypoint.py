"""Tests for the __main__ entrypoint import behavior."""

from __future__ import annotations

import runpy
import sys
from pathlib import Path


def test_main_entrypoint_injects_project_root(monkeypatch):
    """The __main__ module should add the project root to sys.path when executed."""

    script = Path(__file__).resolve().parents[1] / "src" / "automatic_linux_network_repair" / "__main__.py"

    # Simulate running the file directly with the package directory prioritized.
    # Keep the remaining default entries so Python's standard library stays available.
    cleaned_path = [str(script.parent)] + [
        entry for entry in sys.path if entry not in {str(script.parent), str(script.parent.parent)}
    ]
    monkeypatch.setattr(sys, "path", cleaned_path)

    result = runpy.run_path(str(script), run_name="__not_main__")

    assert str(script.parent.parent) in sys.path
    assert "app" in result
