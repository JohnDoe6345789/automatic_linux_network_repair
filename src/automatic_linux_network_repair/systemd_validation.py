"""Validate systemd configuration and unit files under /etc/systemd."""

from __future__ import annotations

import configparser
import dataclasses
import ipaddress
import os
import shutil
import socket
from collections.abc import Callable

from automatic_linux_network_repair.eth_repair.logging_utils import LoggingManager
from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL, ShellRunner
from automatic_linux_network_repair.eth_repair.types import CommandResult

SYSTEMD_UNIT_EXTENSIONS = (
    ".service",
    ".socket",
    ".target",
    ".path",
    ".timer",
    ".mount",
    ".automount",
    ".slice",
    ".scope",
    ".link",
    ".network",
)


@dataclasses.dataclass
class SystemdFileValidation:
    """Result of validating a single systemd file."""

    path: str
    result: CommandResult


@dataclasses.dataclass
class SystemdValidationReport:
    """Aggregate results of validating a systemd configuration tree."""

    available: bool
    unit_files: list[str]
    validations: list[SystemdFileValidation]
    config_issues: list[str]


def _log_issue(issue: str, logger: LoggingManager | None) -> None:
    """Log a configuration issue when a logger is provided."""

    if logger:
        logger.log(f"[FAIL] {issue}")


def _validate_ip_list(values: str, path: str, key: str, logger: LoggingManager | None) -> list[str]:
    """Return issues for a whitespace-delimited list of IP addresses."""

    issues: list[str] = []
    for token in values.split():
        try:
            ipaddress.ip_address(token)
        except ValueError:
            issue = f"{path}: {key} has invalid address '{token}'"
            issues.append(issue)
            _log_issue(issue, logger)
    return issues


def _validate_choice(
    value: str, path: str, key: str, allowed: set[str], logger: LoggingManager | None
) -> list[str]:
    """Return issues when a value is not within the expected set."""

    if value in allowed:
        return []

    issue = f"{path}: {key} should be one of {sorted(allowed)}, got '{value}'"
    _log_issue(issue, logger)
    return [issue]


def _can_resolve_host(host: str) -> bool:
    """Return True when the current resolver can resolve the given host."""

    try:
        socket.getaddrinfo(host, None)
    except OSError:
        return False
    return True


def validate_resolved_conf(
    base_dir: str,
    logger: LoggingManager | None = None,
    resolver: Callable[[str], bool] | None = None,
) -> list[str]:
    """Lint /etc/systemd/resolved.conf for obvious misconfigurations."""

    path = os.path.join(base_dir, "resolved.conf")
    if not os.path.exists(path):
        return []

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with open(path, encoding="utf-8") as handle:
            parser.read_file(handle)
    except (OSError, configparser.Error) as exc:
        issue = f"{path}: failed to parse ({exc})"
        _log_issue(issue, logger)
        return [issue]

    issues: list[str] = []
    if not parser.has_section("Resolve"):
        issue = f"{path}: missing [Resolve] section"
        issues.append(issue)
        _log_issue(issue, logger)
        return issues

    dns_values = parser.get("Resolve", "DNS", fallback="")
    issues.extend(_validate_ip_list(dns_values, path, "DNS", logger))
    dns_tokens = dns_values.split()

    fallback_values = parser.get("Resolve", "FallbackDNS", fallback="")
    issues.extend(_validate_ip_list(fallback_values, path, "FallbackDNS", logger))
    fallback_tokens = fallback_values.split()

    if not dns_tokens and not fallback_tokens:
        resolver_fn = resolver or _can_resolve_host
        if resolver_fn and not resolver_fn("example.com"):
            issue = (
                f"{path}: DNS and FallbackDNS are empty and failed to resolve example.com"
            )
            issues.append(issue)
            _log_issue(issue, logger)

    dnssec = parser.get("Resolve", "DNSSEC", fallback="")
    if dnssec:
        issues.extend(
            _validate_choice(
                dnssec,
                path,
                "DNSSEC",
                {"yes", "no", "allow-downgrade"},
                logger,
            )
        )

    dns_over_tls = parser.get("Resolve", "DNSOverTLS", fallback="")
    if dns_over_tls:
        issues.extend(
            _validate_choice(dns_over_tls, path, "DNSOverTLS", {"yes", "no", "opportunistic"}, logger)
        )

    llmnr = parser.get("Resolve", "LLMNR", fallback="")
    if llmnr:
        issues.extend(_validate_choice(llmnr, path, "LLMNR", {"yes", "no", "resolve"}, logger))

    mdns = parser.get("Resolve", "MulticastDNS", fallback="")
    if mdns:
        issues.extend(_validate_choice(mdns, path, "MulticastDNS", {"yes", "no"}, logger))

    dns_stub = parser.get("Resolve", "DNSStubListener", fallback="")
    if dns_stub:
        issues.extend(
            _validate_choice(dns_stub, path, "DNSStubListener", {"yes", "no", "udp", "tcp", "both"}, logger)
        )

    read_hosts = parser.get("Resolve", "ReadEtcHosts", fallback="")
    if read_hosts:
        issues.extend(_validate_choice(read_hosts, path, "ReadEtcHosts", {"yes", "no"}, logger))

    return issues


def systemd_tools_available() -> bool:
    """Return True if systemctl and systemd-analyze are present in PATH."""

    return shutil.which("systemctl") is not None and shutil.which("systemd-analyze") is not None


def find_systemd_unit_files(base_dir: str) -> list[str]:
    """Return sorted list of unit-like files under base_dir."""

    if not os.path.isdir(base_dir):
        return []

    matches: list[str] = []
    for root, _, files in os.walk(base_dir):
        for name in files:
            if name.endswith(SYSTEMD_UNIT_EXTENSIONS):
                matches.append(os.path.join(root, name))
    return sorted(matches)


def validate_systemd_tree(
    base_dir: str = "/etc/systemd",
    *,
    shell: ShellRunner = DEFAULT_SHELL,
    logger: LoggingManager | None = None,
) -> SystemdValidationReport:
    """Verify all systemd unit files under base_dir using systemd-analyze."""

    config_issues = validate_resolved_conf(base_dir, logger=logger)
    available = systemd_tools_available()
    unit_files = find_systemd_unit_files(base_dir)

    if not available:
        if logger:
            logger.log("systemctl/systemd-analyze not available; skipping systemd validation.")
        return SystemdValidationReport(
            available=False, unit_files=unit_files, validations=[], config_issues=config_issues
        )

    if not unit_files:
        if logger:
            logger.log(f"No systemd unit files found under {base_dir}; nothing to validate.")
        return SystemdValidationReport(available=True, unit_files=[], validations=[], config_issues=config_issues)

    if logger:
        logger.log(f"Validating {len(unit_files)} systemd files under {base_dir}...")

    results: list[SystemdFileValidation] = []
    for path in unit_files:
        result = shell.run_cmd(["systemd-analyze", "verify", path], timeout=15)
        results.append(SystemdFileValidation(path=path, result=result))

        if logger:
            if result.returncode == 0:
                logger.log(f"[OK] {path}")
            else:
                detail = result.stderr.strip() or result.stdout.strip() or f"rc={result.returncode}"
                logger.log(f"[FAIL] {path}: {detail}")

    return SystemdValidationReport(
        available=True,
        unit_files=unit_files,
        validations=results,
        config_issues=config_issues,
    )
