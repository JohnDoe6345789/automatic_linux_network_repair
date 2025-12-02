"""Guardrails to detect stray interactive side effects in source files."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src" / "automatic_linux_network_repair"


def _files_with_pattern(pattern: str) -> set[Path]:
    return {path.relative_to(PROJECT_ROOT) for path in SRC_ROOT.rglob("*.py") if pattern in path.read_text()}


def test_print_calls_limited_to_side_effect_modules() -> None:
    """Ensure print() usage stays inside the side-effect helper modules."""

    expected = {
        Path("src/automatic_linux_network_repair/eth_repair/cli.py"),
        Path("src/automatic_linux_network_repair/eth_repair/menus.py"),
    }
    assert _files_with_pattern("print(") == expected


def test_input_calls_limited_to_side_effect_modules() -> None:
    """Ensure interactive input stays inside designated side-effect modules."""

    expected = {
        Path("src/automatic_linux_network_repair/eth_repair/menus.py"),
        Path("src/automatic_linux_network_repair/eth_repair/repairs.py"),
    }
    assert _files_with_pattern("input(") == expected
