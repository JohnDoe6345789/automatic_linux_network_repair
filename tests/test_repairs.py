"""Tests for DNS repair helpers and side effects."""

from automatic_linux_network_repair.eth_repair import repairs
from tests.helpers import RecordingLogger


class _StubStdin:
    def __init__(self, is_tty: bool):
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def _stub_mode(label: str):
    return type("Mode", (), {"value": label})()


def _apply_dns_common_stubs(monkeypatch):
    monkeypatch.setattr(repairs, "detect_resolv_conf_mode", lambda: (_stub_mode("stub"), "detail"))
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": True, "enabled": False})


def _record_dns_core_calls(calls: list[tuple[bool, bool]]):
    def _record(allow_resolv_conf_edit, dry_run):
        calls.append((allow_resolv_conf_edit, dry_run))

    return _record


def test_fuzzy_dns_skips_prompt_on_non_tty(monkeypatch):
    """The fuzzy DNS path should not prompt when stdin is not a TTY."""

    calls: list[tuple[bool, bool]] = []
    monkeypatch.setattr(repairs, "repair_dns_core", _record_dns_core_calls(calls))
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)
    _apply_dns_common_stubs(monkeypatch)

    effects = repairs.DnsRepairSideEffects(
        logger=RecordingLogger(),
        stdin=_StubStdin(False),
        input_func=lambda prompt: "y",
    )

    repairs.repair_dns_fuzzy_with_confirm(dry_run=True, side_effects=effects)

    assert calls == [(False, True)]
    assert any("Not running on a TTY" in msg for msg in effects.logger.messages)


def test_fuzzy_dns_confirms_and_runs_full_repair(monkeypatch):
    """When the user confirms, the fuzzy flow should escalate to a full repair."""

    calls: list[tuple[bool, bool]] = []
    monkeypatch.setattr(repairs, "repair_dns_core", _record_dns_core_calls(calls))
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)
    _apply_dns_common_stubs(monkeypatch)

    effects = repairs.DnsRepairSideEffects(
        logger=RecordingLogger(),
        stdin=_StubStdin(True),
        input_func=lambda prompt: "y",
    )

    repairs.repair_dns_fuzzy_with_confirm(dry_run=True, side_effects=effects)

    assert calls == [(False, True), (True, True)]
    assert any("DNS still appears broken" in msg for msg in effects.logger.messages)


def test_dns_menu_declines_manual_rewrite_on_non_tty(monkeypatch):
    """The interactive DNS menu should not prompt when stdin is not a TTY."""

    monkeypatch.setattr(repairs, "apply_action", lambda *args, **kwargs: None)
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)
    _apply_dns_common_stubs(monkeypatch)

    effects = repairs.DnsRepairSideEffects(
        logger=RecordingLogger(),
        stdin=_StubStdin(False),
        input_func=lambda prompt: "n",
    )

    repairs.repair_dns_interactive(dry_run=True, side_effects=effects)

    assert any("Not running on a TTY" in msg for msg in effects.logger.messages)
    assert not any("User declined manual" in msg for msg in effects.logger.messages)


def test_repair_no_internet_reports_active_vpn_services(monkeypatch):
    """Active VPN services should be surfaced during generic repair attempts."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "detect_network_managers", lambda: {})
    monkeypatch.setattr(repairs, "tailscale_status", lambda: {"installed": False, "active": False})
    monkeypatch.setattr(repairs, "detect_active_vpn_services", lambda: ["openvpn.service", "wg-quick@wg0.service"])

    repairs.repair_no_internet(dry_run=True)

    assert any("Active VPN services detected" in msg for msg in logger.messages)
    assert any("openvpn.service" in msg for msg in logger.messages)
    assert any("wg-quick@wg0.service" in msg for msg in logger.messages)


def test_repair_no_ipv4_prioritizes_networkmanager(monkeypatch):
    """NetworkManager-managed hosts should renew DHCP via nmcli before other fallbacks."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )

    ipv4_states = iter([False, False, True])
    monkeypatch.setattr(repairs, "interface_has_ipv4", lambda iface: next(ipv4_states))

    managers = {"NetworkManager": True, "systemd-networkd": False, "ifupdown": False}

    repairs.repair_no_ipv4("eth0", managers=managers, dry_run=False)

    expected_first_actions = [
        ["nmcli", "device", "reapply", "eth0"],
        ["nmcli", "device", "connect", "eth0"],
    ]

    assert len(calls) >= len(expected_first_actions)
    assert calls[: len(expected_first_actions)] == expected_first_actions


def test_perform_repairs_iterates_until_scores_drop(monkeypatch):
    """Repairs should progress through multiple suspicions while re-running diagnosis."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)

    diag1 = repairs.Diagnosis(
        "eth0",
        {
            repairs.Suspicion.NO_IPV4: 0.9,
            repairs.Suspicion.NO_ROUTE: 0.7,
        },
    )
    diag2 = repairs.Diagnosis("eth0", {repairs.Suspicion.NO_ROUTE: 0.65})
    diag3 = repairs.Diagnosis("eth0", {repairs.Suspicion.NO_ROUTE: 0.2})

    diagnoses = iter([diag2, diag3])
    monkeypatch.setattr(repairs, "fuzzy_diagnose", lambda iface: next(diagnoses))

    applied: list[repairs.Suspicion] = []

    def _fake_apply(self, suspicion):
        applied.append(suspicion)

    monkeypatch.setattr(repairs.EthernetRepairCoordinator, "_apply_repair", _fake_apply, raising=False)

    coordinator = repairs.EthernetRepairCoordinator("eth0", dry_run=True, allow_resolv_conf_edit=False)
    coordinator.perform_repairs(diag1)

    assert applied == [repairs.Suspicion.NO_IPV4, repairs.Suspicion.NO_ROUTE]
    assert any("Repair iteration 1" in msg for msg in logger.messages)
    assert any("Re-running diagnosis after attempted repair" in msg for msg in logger.messages)


def test_perform_repairs_stops_when_no_actions_remain(monkeypatch):
    """Once all actionable suspicions are attempted, the loop should exit."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)

    diag1 = repairs.Diagnosis("eth0", {repairs.Suspicion.NO_ROUTE: 0.8})
    diag2 = repairs.Diagnosis("eth0", {repairs.Suspicion.NO_ROUTE: 0.75})

    monkeypatch.setattr(repairs, "fuzzy_diagnose", lambda iface: diag2)

    applied: list[repairs.Suspicion] = []

    def _fake_apply(self, suspicion):
        applied.append(suspicion)

    monkeypatch.setattr(repairs.EthernetRepairCoordinator, "_apply_repair", _fake_apply, raising=False)

    coordinator = repairs.EthernetRepairCoordinator("eth0", dry_run=True, allow_resolv_conf_edit=False)
    coordinator.perform_repairs(diag1)

    assert applied == [repairs.Suspicion.NO_ROUTE]
    assert any("No further repair actions remain" in msg for msg in logger.messages)
