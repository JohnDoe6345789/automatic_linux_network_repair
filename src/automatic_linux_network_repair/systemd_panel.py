"""Render systemd configuration dumps as rich panels for quick review."""

from __future__ import annotations

import configparser
import os
import shutil
from collections.abc import Callable, Mapping
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL, ShellRunner
from automatic_linux_network_repair.eth_repair.types import CommandResult


def parse_systemd_dump(dump: str) -> dict[str, str]:
    """Return mapping of file paths to their raw contents from a dump string.

    Recognizes both the ``# FILE: <path>`` markers used by generated dumps and
    the ``# /path/to/unit`` headers that ``systemd-analyze cat-config`` emits
    directly. Everything between one marker and the next is treated as the file
    contents. Leading and trailing whitespace for each file body is stripped,
    but the original line ordering is preserved.
    """

    files: dict[str, list[str]] = {}
    current_path: str | None = None
    buffer: list[str] = []

    def _extract_path(header_line: str) -> str | None:
        if header_line.startswith("# FILE: "):
            return header_line.split("# FILE: ", 1)[1].strip()

        if header_line.startswith("#/"):
            candidate = header_line[1:].strip()
            if candidate.startswith("/"):
                return candidate

        if header_line.startswith("# "):
            candidate = header_line[2:].strip()
            if candidate.startswith("/"):
                return candidate

        return None

    for line in dump.splitlines():
        path = _extract_path(line)
        if path:
            if current_path is not None:
                files[current_path] = "\n".join(buffer).strip("\n")
            current_path = path
            buffer = []
            continue

        if current_path is None:
            continue

        if not buffer and line.startswith("########################################"):
            continue

        buffer.append(line)

    if current_path is not None:
        files[current_path] = "\n".join(buffer).strip("\n")

    return files


def _extract_active_settings(body: str) -> dict[str, dict[str, str]]:
    """Parse non-comment INI settings from a systemd config body.

    Commented and empty lines are ignored. If parsing fails, an empty mapping is
    returned so that the caller can display "No active settings" for that file.
    """

    cleaned: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(";"):
            continue
        cleaned.append(stripped)

    if not cleaned:
        return {}

    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str

    try:
        parser.read_string("\n".join(cleaned))
    except configparser.Error:
        return {}

    settings: dict[str, dict[str, str]] = {}
    for section in parser.sections():
        settings[section] = dict(parser.items(section))
    return settings


def _extract_commented_settings(body: str) -> dict[str, dict[str, str]]:
    """Return commented-out settings organized by section.

    Only lines that look like ``#Key=value`` are captured. Other comment lines
    (e.g., descriptive prose or URLs) are ignored to avoid polluting the schema
    with non-config data.
    """

    commented: dict[str, dict[str, str]] = {}
    section: str | None = None

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line.strip("[]")
            continue

        if not section:
            continue

        if not (line.startswith("#") or line.startswith(";")):
            continue

        candidate = line.lstrip("#;").strip()
        if not candidate or candidate.startswith("#"):
            continue

        if "=" not in candidate:
            continue

        key, value = candidate.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key.isidentifier():
            continue

        commented.setdefault(section, {})[key] = value

    return {section: values for section, values in commented.items() if values}


def render_systemd_panel(files: Mapping[str, str]) -> Panel:
    """Build a rich Panel summarizing active settings from parsed files."""

    table = Table("File", "Active settings", expand=True)
    for path, body in files.items():
        settings = _extract_active_settings(body)
        if not settings:
            table.add_row(path, "No active settings")
            continue

        lines: list[str] = []
        for section, values in settings.items():
            lines.append(f"[{section}]")
            for key, value in values.items():
                lines.append(f"{key}={value}")
        table.add_row(path, "\n".join(lines))

    return Panel(table, title="Systemd configuration", subtitle="Active values from dump")


def print_systemd_panel(dump: str, console: Console | None = None) -> None:
    """Render and print a systemd configuration panel to the provided console."""

    parsed = parse_systemd_dump(dump)
    output_console = console or Console(force_terminal=False)
    printer = output_console.print
    printer(render_systemd_panel(parsed))


def systemd_schema_from_dump(dump: str) -> dict[str, dict[str, Any]]:
    """Return a JSON-serializable schema from a dump string."""

    parsed = parse_systemd_dump(dump)
    schema: dict[str, dict[str, Any]] = {}
    for path, body in parsed.items():
        schema[path] = {
            "active_settings": _extract_active_settings(body),
            "commented_settings": _extract_commented_settings(body),
        }
    return schema


def systemd_dump_from_schema(schema: Mapping[str, Mapping[str, Any]]) -> str:
    """Build a ``systemd-analyze cat-config`` style dump from a schema mapping."""

    lines: list[str] = []

    for path in sorted(schema):
        entry = schema[path]
        active_settings = entry.get("active_settings", {}) or {}
        commented_settings = entry.get("commented_settings", {}) or {}

        if lines:
            lines.append("")

        lines.append(f"# {path}")

        sections = sorted(set(active_settings) | set(commented_settings))
        for section in sections:
            lines.append("")
            lines.append(f"[{section}]")

            for key, value in sorted(commented_settings.get(section, {}).items()):
                lines.append(f"#{key}={value}")

            for key, value in sorted(active_settings.get(section, {}).items()):
                lines.append(f"{key}={value}")

        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def collect_systemd_files(base_dir: str = "/etc/systemd") -> list[str]:
    """Return sorted list of regular files under the given systemd directory."""

    if not os.path.isdir(base_dir):
        return []

    files: list[str] = []
    for root, _, names in os.walk(base_dir):
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path):
                files.append(path)

    return sorted(files)


def generate_systemd_dump(base_dir: str = "/etc/systemd", *, shell: ShellRunner = DEFAULT_SHELL) -> CommandResult:
    """Run ``systemd-analyze cat-config`` against every file under base_dir."""

    files = collect_systemd_files(base_dir)
    cmd = ["systemd-analyze", "cat-config", *files]

    if not files:
        return CommandResult(cmd=cmd, returncode=1, stdout="", stderr=f"No files found under {base_dir}")

    if shutil.which("systemd-analyze") is None:
        return CommandResult(cmd=cmd, returncode=127, stdout="", stderr="systemd-analyze not available")

    return shell.run_cmd(cmd, timeout=30)


def _build_dropin_path(target: str, override_dir: str | None = None) -> str:
    """Return the path to a drop-in file for ``target``.

    If ``override_dir`` is provided, it is used directly; otherwise ``<target>.d``
    is used alongside the original file. The resulting path always ends with a
    stable file name so repeated edits do not create multiple files.
    """

    directory = override_dir or f"{target}.d"
    return os.path.join(directory, "99-automatic-linux-network-repair.conf")


def interactive_edit_systemd_dump(
    dump: str,
    *,
    dropin_dir: str | None = None,
    prompt: Callable[[str], str] | None = None,
    console: Console | None = None,
) -> str | None:
    """Interactively edit a setting from a dump and write a drop-in file.

    Returns the path to the created drop-in file, or ``None`` if the session was
    aborted. Only active (non-commented) settings are offered for editing so the
    changes reflect current behavior.
    """

    prompt_fn = prompt or input
    output_console = console or Console(force_terminal=False)
    emit = output_console.print

    parsed = parse_systemd_dump(dump)
    if not parsed:
        emit("No files available in dump; nothing to edit.")
        return None

    file_items = list(parsed.items())
    emit("Available files:")
    for idx, (path, _) in enumerate(file_items, start=1):
        emit(f"  {idx}) {path}")

    while True:
        choice = prompt_fn("Select file number to edit (or q to quit): ").strip()
        if choice.lower().startswith("q"):
            return None
        try:
            file_index = int(choice) - 1
        except ValueError:
            emit("Please enter a number from the list or 'q' to exit.")
            continue
        if 0 <= file_index < len(file_items):
            break
        emit("Selection out of range; try again.")

    target_path, body = file_items[file_index]
    active_settings = _extract_active_settings(body)
    if not active_settings:
        emit(f"No active settings found in {target_path}; nothing to edit.")
        return None

    sections = sorted(active_settings)
    emit("Available sections and keys:")
    for s_idx, section in enumerate(sections, start=1):
        keys = ", ".join(sorted(active_settings[section])) or "<no keys>"
        emit(f"  {s_idx}) [{section}] -> {keys}")

    while True:
        s_choice = prompt_fn("Select section number (or q to quit): ").strip()
        if s_choice.lower().startswith("q"):
            return None
        try:
            section_index = int(s_choice) - 1
        except ValueError:
            emit("Please enter a number from the list or 'q' to exit.")
            continue
        if 0 <= section_index < len(sections):
            break
        emit("Selection out of range; try again.")

    section = sections[section_index]
    keys = sorted(active_settings[section])
    for k_idx, key in enumerate(keys, start=1):
        emit(f"  {k_idx}) {key} = {active_settings[section][key]}")

    while True:
        k_choice = prompt_fn("Select key number (or q to quit): ").strip()
        if k_choice.lower().startswith("q"):
            return None
        try:
            key_index = int(k_choice) - 1
        except ValueError:
            emit("Please enter a number from the list or 'q' to exit.")
            continue
        if 0 <= key_index < len(keys):
            break
        emit("Selection out of range; try again.")

    key = keys[key_index]
    new_value = prompt_fn(f"Enter new value for {key} (current: {active_settings[section][key]}): ")

    dropin_path = _build_dropin_path(target_path, override_dir=dropin_dir)
    os.makedirs(os.path.dirname(dropin_path), exist_ok=True)
    content = f"[{section}]\n{key}={new_value}\n"
    with open(dropin_path, "w", encoding="utf-8") as handle:
        handle.write(content)

    emit(f"Wrote drop-in to {dropin_path}")
    emit(content)
    return dropin_path
