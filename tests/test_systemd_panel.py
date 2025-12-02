"""Tests for rendering systemd configuration dumps as panels."""

import json

from rich.console import Console
from typer.testing import CliRunner

from automatic_linux_network_repair import systemd_panel, systemd_schemas
from automatic_linux_network_repair.cli import app
from automatic_linux_network_repair.eth_repair.types import CommandResult

SAMPLE_SCHEMA = systemd_schemas.load_sample_schema()
SYSTEMD_DUMP = systemd_panel.systemd_dump_from_schema(SAMPLE_SCHEMA)
CAT_CONFIG_SAMPLE = """# /usr/lib/systemd/system/systemd-networkd.service
#  SPDX-License-Identifier: LGPL-2.1-or-later
#
[Unit]
Description=Network Configuration

[Service]
ExecStart=!!/lib/systemd/systemd-networkd

# /usr/lib/systemd/system/colord.service
[Unit]
Description=Manage, Install and Generate Color Profiles

[Service]
Type=dbus
ExecStart=/usr/libexec/colord
"""


def test_parse_systemd_dump_extracts_all_files():
    files = systemd_panel.parse_systemd_dump(SYSTEMD_DUMP)

    assert SYSTEMD_DUMP.splitlines()[0].startswith("# /")
    assert len(files) == 20
    assert "/etc/systemd/logind.conf" in files
    assert files["/etc/systemd/system/tmp.mount"].startswith("########################################") is False


def test_systemd_schema_from_dump_contains_active_settings():
    schema = systemd_panel.systemd_schema_from_dump(SYSTEMD_DUMP)

    assert "/etc/systemd/logind.conf" in schema
    logind_settings = schema["/etc/systemd/logind.conf"]["active_settings"]
    assert logind_settings["Login"]["HandlePowerKey"] == "ignore"

    resolved_settings = schema["/etc/systemd/resolved.conf"]["active_settings"]
    assert resolved_settings["Resolve"]["DNS"] == "1.1.1.1 8.8.8.8"


def test_systemd_schema_includes_commented_settings():
    schema = systemd_panel.systemd_schema_from_dump(SYSTEMD_DUMP)

    journald = schema["/etc/systemd/journald.conf"]["commented_settings"]["Journal"]
    assert journald["Storage"] == "auto"
    assert journald["MaxLevelWall"] == "emerg"


def test_parse_systemd_dump_supports_raw_cat_config_output():
    files = systemd_panel.parse_systemd_dump(CAT_CONFIG_SAMPLE)

    assert files == {
        "/usr/lib/systemd/system/systemd-networkd.service": (
            "#  SPDX-License-Identifier: LGPL-2.1-or-later\n#\n[Unit]\n"
            "Description=Network Configuration\n\n[Service]\n"
            "ExecStart=!!/lib/systemd/systemd-networkd"
        ),
        "/usr/lib/systemd/system/colord.service": (
            "[Unit]\nDescription=Manage, Install and Generate Color Profiles\n\n[Service]\n"
            "Type=dbus\nExecStart=/usr/libexec/colord"
        ),
    }


def test_sample_schema_file_matches_dump():
    saved_schema = systemd_schemas.load_sample_schema()
    generated_schema = systemd_panel.systemd_schema_from_dump(SYSTEMD_DUMP)

    assert saved_schema == generated_schema


def test_dump_round_trips_schema():
    regenerated_schema = systemd_panel.systemd_schema_from_dump(SYSTEMD_DUMP)

    assert regenerated_schema == SAMPLE_SCHEMA


def test_render_systemd_panel_shows_active_values():
    files = systemd_panel.parse_systemd_dump(SYSTEMD_DUMP)
    panel = systemd_panel.render_systemd_panel(files)
    console = Console(record=True, force_terminal=False)
    console.print(panel)
    output = console.export_text()

    assert "HandlePowerKey=ignore" in output
    assert "MulticastDNS=no" in output
    assert "RuntimeWatchdogSec=5min" in output


def test_cli_command_prints_panel(tmp_path):
    dump_path = tmp_path / "dump.txt"
    dump_path.write_text(SYSTEMD_DUMP)
    runner = CliRunner()

    result = runner.invoke(app, ["systemd-panel", "--dump-file", str(dump_path)])

    assert result.exit_code == 0
    assert "Systemd configuration" in result.output
    assert "HandlePowerKey=ignore" in result.output


def test_cli_command_writes_schema_json(tmp_path):
    dump_path = tmp_path / "dump.txt"
    dump_path.write_text(SYSTEMD_DUMP)
    schema_path = tmp_path / "schema.json"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "systemd-panel",
            "--dump-file",
            str(dump_path),
            "--schema-json",
            str(schema_path),
        ],
    )

    assert result.exit_code == 0
    saved_schema = json.loads(schema_path.read_text())
    assert saved_schema["/etc/systemd/logind.conf"]["active_settings"]["Login"]["HandlePowerKey"] == "ignore"
    assert saved_schema["/etc/systemd/journald.conf"]["commented_settings"]["Journal"]["Storage"] == "auto"


def test_collect_systemd_files_returns_sorted_entries(tmp_path):
    (tmp_path / "b.conf").write_text("b")
    (tmp_path / "a.conf").write_text("a")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "c.service").write_text("c")

    files = systemd_panel.collect_systemd_files(str(tmp_path))

    assert files == [
        str(tmp_path / "a.conf"),
        str(tmp_path / "b.conf"),
        str(nested / "c.service"),
    ]


def test_generate_systemd_dump_runs_cat_config(monkeypatch, tmp_path):
    (tmp_path / "one.conf").write_text("one")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "two.service").write_text("two")

    class StubShell:
        def __init__(self) -> None:
            self.calls: list[tuple[list[str], int]] = []

        def run_cmd(self, cmd: list[str], timeout: int = 5) -> CommandResult:
            self.calls.append((cmd, timeout))
            return CommandResult(cmd=cmd, returncode=0, stdout="dumped", stderr="")

    monkeypatch.setattr(systemd_panel.shutil, "which", lambda name: "/usr/bin/systemd-analyze")
    shell = StubShell()

    result = systemd_panel.generate_systemd_dump(str(tmp_path), shell=shell)

    assert result.stdout == "dumped"
    assert shell.calls
    cat_cmd, timeout = shell.calls[0]
    assert cat_cmd[:2] == ["systemd-analyze", "cat-config"]
    assert timeout == 30
    assert str(tmp_path / "one.conf") in cat_cmd
    assert str(nested / "two.service") in cat_cmd


def test_cli_command_generates_dump_when_no_file(monkeypatch, tmp_path):
    runner = CliRunner()
    fake_result = CommandResult(cmd=[], returncode=0, stdout=SYSTEMD_DUMP, stderr="")

    monkeypatch.setattr(systemd_panel, "generate_systemd_dump", lambda base_dir: fake_result)

    result = runner.invoke(app, ["systemd-panel", "--path", str(tmp_path)])

    assert result.exit_code == 0
    assert "Systemd configuration" in result.output
    assert "HandlePowerKey=ignore" in result.output


def test_build_dropin_path_uses_override_dir():
    path = systemd_panel._build_dropin_path("/etc/systemd/logind.conf", override_dir="/tmp/out")

    assert path == "/tmp/out/99-automatic-linux-network-repair.conf"


def test_interactive_edit_systemd_dump_writes_dropin(tmp_path):
    responses = iter(["2", "1", "1", "new-ignore", "y"])
    console = Console(record=True, force_terminal=False)

    dropin_path = systemd_panel.interactive_edit_systemd_dump(
        SYSTEMD_DUMP,
        dropin_dir=str(tmp_path),
        prompt=lambda message: next(responses),
        console=console,
    )

    expected_path = tmp_path / "99-automatic-linux-network-repair.conf"
    assert dropin_path == str(expected_path)
    assert expected_path.read_text() == "[Login]\nHandlePowerKey=new-ignore\n"


def test_interactive_edit_systemd_dump_respects_abort(tmp_path):
    responses = iter(["2", "1", "1", "new-val", "n"])
    console = Console(record=True, force_terminal=False)

    dropin_path = systemd_panel.interactive_edit_systemd_dump(
        SYSTEMD_DUMP,
        dropin_dir=str(tmp_path),
        prompt=lambda message: next(responses),
        console=console,
    )

    assert dropin_path is None
    assert list(tmp_path.glob("*")) == []


def test_cli_systemd_edit_writes_dropin(tmp_path):
    dump_path = tmp_path / "dump.txt"
    dump_path.write_text(SYSTEMD_DUMP)
    dropin_dir = tmp_path / "override"
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["systemd-edit", "--dump-file", str(dump_path), "--dropin-dir", str(dropin_dir)],
        input="2\n1\n1\nnew-ignore\ny\n",
    )

    expected_path = dropin_dir / "99-automatic-linux-network-repair.conf"
    assert result.exit_code == 0
    assert expected_path.exists()
    assert expected_path.read_text() == "[Login]\nHandlePowerKey=new-ignore\n"
