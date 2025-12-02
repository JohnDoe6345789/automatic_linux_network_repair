from __future__ import annotations

import sys
from pathlib import Path


def _ensure_package_on_path() -> None:
    """Insert the project root into ``sys.path`` when run as a script.

    PyInstaller and direct ``python __main__.py`` execution resolve imports as if
    this file lives at the top of ``sys.path``. Without the parent directory on
    the path, ``automatic_linux_network_repair`` cannot be imported with
    absolute imports, resulting in ``ImportError: attempted relative import with
    no known parent package``. Adding the parent directory ensures the package
    remains importable in both package and stand-alone contexts.
    """

    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)


def _load_app():
    _ensure_package_on_path()
    from automatic_linux_network_repair.cli import app as cli_app

    return cli_app


app = _load_app()


def main() -> None:
    """Entrypoint for running the CLI application."""

    app()


if __name__ == "__main__":
    main()
