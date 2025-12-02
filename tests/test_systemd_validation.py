"""Tests for systemd validation helpers."""

from automatic_linux_network_repair import systemd_validation as sv
from automatic_linux_network_repair.eth_repair.types import CommandResult


class _StubLogger:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, msg: str) -> None:  # pragma: no cover - trivial logging helper
        self.messages.append(msg)


class _StubShell:
    def __init__(self, results: dict[str, CommandResult]):
        self.results = dict(results)
        self.calls: list[tuple[list[str], int]] = []

    def run_cmd(self, cmd: list[str], timeout: int = 5) -> CommandResult:
        self.calls.append((cmd, timeout))
        path = cmd[-1]
        return self.results[path]


def test_validate_systemd_tree_skips_without_tools(monkeypatch, tmp_path):
    """Validation should short-circuit when systemd tooling is unavailable."""

    monkeypatch.setattr(sv.shutil, "which", lambda name: None)
    logger = _StubLogger()
    shell = _StubShell({})

    report = sv.validate_systemd_tree(base_dir=str(tmp_path), shell=shell, logger=logger)

    assert report.available is False
    assert report.validations == []
    assert report.config_issues == []
    assert any("skipping systemd validation" in msg for msg in logger.messages)


def test_validate_systemd_tree_handles_empty_directory(monkeypatch, tmp_path):
    """If no unit files exist, validation should report availability and exit early."""

    monkeypatch.setattr(sv.shutil, "which", lambda name: f"/usr/bin/{name}")
    logger = _StubLogger()
    shell = _StubShell({})

    report = sv.validate_systemd_tree(base_dir=str(tmp_path), shell=shell, logger=logger)

    assert report.available is True
    assert report.unit_files == []
    assert report.validations == []
    assert report.config_issues == []
    assert any("No systemd unit files" in msg for msg in logger.messages)


def test_validate_systemd_tree_runs_verifications(monkeypatch, tmp_path):
    """Unit files should be validated and their results returned."""

    monkeypatch.setattr(sv.shutil, "which", lambda name: f"/usr/bin/{name}")
    (tmp_path / "network").mkdir()
    good = tmp_path / "network" / "eth0.service"
    good.write_text("[Unit]\nDescription=good service\n")
    bad = tmp_path / "broken.timer"
    bad.write_text("[Unit]\nDescription=bad timer\n")
    ignored = tmp_path / "readme.txt"
    ignored.write_text("ignore me")

    logger = _StubLogger()
    results = {
        str(good): CommandResult(cmd=[], returncode=0, stdout="", stderr=""),
        str(bad): CommandResult(cmd=[], returncode=1, stdout="", stderr="invalid section"),
    }
    shell = _StubShell(results)

    report = sv.validate_systemd_tree(base_dir=str(tmp_path), shell=shell, logger=logger)

    assert report.available is True
    assert len(report.unit_files) == 2
    expected_calls = {
        ("systemd-analyze", "verify", str(good)),
        ("systemd-analyze", "verify", str(bad)),
    }
    assert {tuple(call[0]) for call in shell.calls} == expected_calls
    assert all(timeout == 15 for _, timeout in shell.calls)

    statuses = {validation.path: validation.result.returncode for validation in report.validations}
    assert statuses[str(good)] == 0
    assert statuses[str(bad)] == 1
    assert report.config_issues == []
    assert any("[OK]" in msg for msg in logger.messages)
    assert any("[FAIL]" in msg for msg in logger.messages)
    assert str(ignored) not in report.unit_files


def test_validate_systemd_tree_reports_resolved_conf_issues(monkeypatch, tmp_path):
    """Misconfigured resolved.conf entries should be surfaced as config issues."""

    monkeypatch.setattr(sv.shutil, "which", lambda name: None)
    resolved = tmp_path / "resolved.conf"
    resolved.write_text(
        """
[Resolve]
DNS=1.1.1.1 127.0.0.300
FallbackDNS=abcd::1
DNSSEC=maybe
DNSOverTLS=auto
LLMNR=maybe
MulticastDNS=maybe
DNSStubListener=udp4
ReadEtcHosts=perhaps
""".strip()
    )

    logger = _StubLogger()
    report = sv.validate_systemd_tree(base_dir=str(tmp_path), shell=_StubShell({}), logger=logger)

    assert report.available is False
    assert len(report.config_issues) >= 5
    assert any("invalid address '127.0.0.300'" in issue for issue in report.config_issues)
    assert any("DNSSEC" in issue for issue in report.config_issues)
    assert any("DNSOverTLS" in issue for issue in report.config_issues)
    assert any(issue.startswith(str(resolved)) for issue in report.config_issues)
    assert any("[FAIL]" in msg for msg in logger.messages)


def test_validate_systemd_tree_accepts_valid_resolved_conf(monkeypatch, tmp_path):
    """Well-formed resolved.conf entries should not produce issues."""

    monkeypatch.setattr(sv.shutil, "which", lambda name: f"/usr/bin/{name}")
    resolved = tmp_path / "resolved.conf"
    resolved.write_text(
        """
[Resolve]
DNS=1.1.1.1 2606:4700:4700::1111
FallbackDNS=8.8.8.8
DNSSEC=yes
DNSOverTLS=opportunistic
LLMNR=no
MulticastDNS=yes
DNSStubListener=udp
ReadEtcHosts=yes
""".strip()
    )

    report = sv.validate_systemd_tree(base_dir=str(tmp_path), shell=_StubShell({}), logger=_StubLogger())

    assert report.available is True
    assert report.config_issues == []


def test_validate_resolved_conf_flags_empty_dns_when_resolution_fails(tmp_path):
    """Empty DNS values should be reported if name resolution fails."""

    resolved = tmp_path / "resolved.conf"
    resolved.write_text("[Resolve]\n")

    calls: list[str] = []

    def fake_resolver(host: str) -> bool:
        calls.append(host)
        return False

    logger = _StubLogger()
    issues = sv.validate_resolved_conf(str(tmp_path), logger=logger, resolver=fake_resolver)

    assert any("empty" in issue and "example.com" in issue for issue in issues)
    assert calls == ["example.com"]
    assert any("[FAIL]" in msg for msg in logger.messages)
