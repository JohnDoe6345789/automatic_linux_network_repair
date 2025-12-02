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


def test_repair_interface_missing_logs_hint(monkeypatch):
    """Absent interfaces should surface explanatory hints."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)

    repairs.repair_interface_missing("eth9")

    assert any("Interface does not exist" in msg for msg in logger.messages)
    assert any("Check dmesg" in msg for msg in logger.messages)


def test_repair_link_down_invokes_ip(monkeypatch):
    """Link-down repair should call ip link up for the interface."""

    calls: list[tuple[str, list[str], bool]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append((label, cmd, dry_run)),
    )

    repairs.repair_link_down("eth0", dry_run=True)

    assert calls == [
        (
            "Bring eth0 link UP via ip",
            ["ip", "link", "set", "eth0", "up"],
            True,
        )
    ]


def test_repair_no_ipv4_succeeds_after_nm_reapply(monkeypatch):
    """When NM reapply returns IPv4, the flow should stop early."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )
    monkeypatch.setattr(repairs, "interface_has_ipv4", lambda iface: True)

    repairs.repair_no_ipv4(
        "eth0",
        managers={"NetworkManager": True, "systemd-networkd": False, "ifupdown": False},
        dry_run=False,
    )

    assert calls == [["nmcli", "device", "reapply", "eth0"]]


def test_repair_no_ipv4_succeeds_after_networkd(monkeypatch):
    """systemd-networkd restart should short-circuit when it restores IPv4."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )
    monkeypatch.setattr(repairs, "interface_has_ipv4", lambda iface: True)

    repairs.repair_no_ipv4(
        "eth0",
        managers={"NetworkManager": False, "systemd-networkd": True, "ifupdown": False},
        dry_run=False,
    )

    assert calls == [["systemctl", "restart", "systemd-networkd"]]


def test_repair_no_ipv4_succeeds_after_ifupdown(monkeypatch):
    """ifupdown-managed hosts should ifdown/ifup before dhclient."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )
    monkeypatch.setattr(repairs, "interface_has_ipv4", lambda iface: True)

    repairs.repair_no_ipv4(
        "eth0",
        managers={"NetworkManager": False, "systemd-networkd": False, "ifupdown": True},
        dry_run=False,
    )

    assert calls == [["ifdown", "eth0"], ["ifup", "eth0"]]


def test_repair_no_ipv4_falls_back_to_dhclient(monkeypatch):
    """When all managers fail, dhclient should be invoked and warn about DHCP."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: logger.log(f"ACTION: {cmd}"),
    )
    monkeypatch.setattr(repairs, "interface_has_ipv4", lambda iface: False)

    repairs.repair_no_ipv4(
        "eth0",
        managers={"NetworkManager": False, "systemd-networkd": False, "ifupdown": False},
        dry_run=False,
    )

    assert any("dhclient" in msg for msg in logger.messages)
    assert any("Still no IPv4" in msg for msg in logger.messages)


def test_repair_no_route_prefers_network_manager(monkeypatch):
    """The default route repair should restart the detected manager."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )
    monkeypatch.setattr(
        repairs,
        "detect_network_managers",
        lambda: {"NetworkManager": True, "systemd-networkd": False, "ifupdown": False},
    )

    repairs.repair_no_route(dry_run=True)

    assert calls == [["systemctl", "restart", "NetworkManager"]]


def test_repair_no_route_logs_when_manager_unknown(monkeypatch):
    """If no known manager is detected, a hint should be logged."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "detect_network_managers", lambda: {})
    monkeypatch.setattr(repairs, "apply_action", lambda *args, **kwargs: None)

    repairs.repair_no_route(dry_run=False)

    assert any("No known network manager" in msg for msg in logger.messages)


def test_repair_no_internet_handles_tailscale(monkeypatch):
    """Tailscale installation state should be surfaced in generic repair."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "detect_network_managers", lambda: {})
    monkeypatch.setattr(
        repairs,
        "tailscale_status",
        lambda: {"installed": True, "active": True},
    )
    monkeypatch.setattr(repairs, "detect_active_vpn_services", lambda: [])

    repairs.repair_no_internet(dry_run=True)

    assert any("Tailscale detected" in msg for msg in logger.messages)


def test_repair_no_internet_uses_network_manager(monkeypatch):
    """Restart NetworkManager immediately when it is present."""

    calls: list[list[str]] = []
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: calls.append(cmd),
    )
    monkeypatch.setattr(
        repairs,
        "detect_network_managers",
        lambda: {"NetworkManager": True},
    )
    monkeypatch.setattr(repairs, "tailscale_status", lambda: {"installed": False, "active": False})
    monkeypatch.setattr(repairs, "detect_active_vpn_services", lambda: [])

    repairs.repair_no_internet(dry_run=False)

    assert calls == [["systemctl", "restart", "NetworkManager"]]


def test_repair_dns_core_restarts_systemd_resolved(monkeypatch):
    """Active systemd-resolved should be restarted and exit on success."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": True})
    monkeypatch.setattr(
        repairs,
        "apply_action",
        lambda label, cmd, dry_run: logger.log(f"ACTION: {cmd}"),
    )
    monkeypatch.setattr(repairs, "dns_resolves", lambda: True)

    repairs.repair_dns_core(allow_resolv_conf_edit=False, dry_run=False)

    assert any("systemd-resolved" in msg for msg in logger.messages)
    assert not any("resolv.conf editing" in msg for msg in logger.messages)


def test_repair_dns_core_respects_no_edit_flag(monkeypatch):
    """Without resolv.conf permission, the function should return early."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": False})
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)
    monkeypatch.setattr(repairs, "apply_action", lambda *args, **kwargs: None)

    repairs.repair_dns_core(allow_resolv_conf_edit=False, dry_run=True)

    assert any("resolv.conf editing is disabled" in msg for msg in logger.messages)


def test_repair_dns_core_rewrites_resolv_conf(monkeypatch):
    """When allowed, DNS core should back up and rewrite resolv.conf."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": False})
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)

    actions: list[str] = []
    monkeypatch.setattr(repairs, "backup_resolv_conf", lambda dry_run: actions.append("backup"))
    monkeypatch.setattr(repairs, "set_resolv_conf_manual_public", lambda dry_run: actions.append("rewrite"))

    repairs.repair_dns_core(allow_resolv_conf_edit=True, dry_run=False)

    assert actions == ["backup", "rewrite"]
    assert any("resolv.conf rewrite" in msg for msg in logger.messages)


def test_repair_dns_fuzzy_returns_after_limited_fix(monkeypatch):
    """The fuzzy flow should stop if DNS is OK after limited repair."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "repair_dns_core", lambda allow_resolv_conf_edit, dry_run: None)
    monkeypatch.setattr(repairs, "dns_resolves", lambda: True)
    monkeypatch.setattr(repairs, "detect_resolv_conf_mode", lambda: (_stub_mode("stub"), "detail"))
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": True, "enabled": True})

    effects = repairs.DnsRepairSideEffects(logger=logger, stdin=_StubStdin(True), input_func=lambda p: "n")

    repairs.repair_dns_fuzzy_with_confirm(dry_run=True, side_effects=effects)

    assert any("DNS OK after limited DNS repair" in msg for msg in logger.messages)


def test_repair_dns_interactive_logs_decline(monkeypatch):
    """Interactive DNS menu should log when the user declines a rewrite."""

    logger = RecordingLogger()
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", logger)
    monkeypatch.setattr(repairs, "systemd_resolved_status", lambda: {"active": False, "enabled": True})
    monkeypatch.setattr(repairs, "dns_resolves", lambda: False)
    monkeypatch.setattr(repairs, "detect_resolv_conf_mode", lambda: (_stub_mode("stub"), "detail"))
    monkeypatch.setattr(repairs, "apply_action", lambda *args, **kwargs: None)

    effects = repairs.DnsRepairSideEffects(logger=logger, stdin=_StubStdin(True), input_func=lambda p: "n")

    repairs.repair_dns_interactive(dry_run=True, side_effects=effects)

    assert any("User declined manual" in msg for msg in logger.messages)


def test_coordinator_apply_repair_routes_to_dns(monkeypatch):
    """_apply_repair should call DNS repair helpers based on permissions."""

    called: list[str] = []
    monkeypatch.setattr(repairs, "repair_dns_fuzzy_with_confirm", lambda dry_run: called.append("fuzzy"))
    monkeypatch.setattr(
        repairs,
        "repair_dns_core",
        lambda allow_resolv_conf_edit, dry_run: called.append(f"core-{allow_resolv_conf_edit}-{dry_run}"),
    )

    coord = repairs.EthernetRepairCoordinator("eth0", dry_run=False, allow_resolv_conf_edit=True)
    coord._repair_dns()

    coord_allow_false = repairs.EthernetRepairCoordinator("eth0", dry_run=True, allow_resolv_conf_edit=False)
    coord_allow_false._repair_dns()

    assert called == ["fuzzy", "core-False-True"]


def test_coordinator_apply_repair_dispatches(monkeypatch):
    """Each suspicion should dispatch to its corresponding repair function."""

    calls: list[str] = []
    monkeypatch.setattr(repairs, "repair_interface_missing", lambda iface: calls.append(f"missing:{iface}"))
    monkeypatch.setattr(repairs, "repair_link_down", lambda iface, dry_run: calls.append(f"link:{iface}:{dry_run}"))
    monkeypatch.setattr(
        repairs,
        "repair_no_ipv4",
        lambda iface, managers, dry_run: calls.append(f"ipv4:{iface}:{dry_run}:{managers}"),
    )
    monkeypatch.setattr(repairs, "detect_network_managers", lambda: {"NetworkManager": True})
    monkeypatch.setattr(repairs, "repair_no_route", lambda dry_run: calls.append(f"route:{dry_run}"))
    monkeypatch.setattr(repairs, "DEFAULT_LOGGER", RecordingLogger())

    coord = repairs.EthernetRepairCoordinator("eth0", dry_run=True, allow_resolv_conf_edit=False)

    for suspicion in (
        repairs.Suspicion.INTERFACE_MISSING,
        repairs.Suspicion.LINK_DOWN,
        repairs.Suspicion.NO_IPV4,
        repairs.Suspicion.NO_ROUTE,
        repairs.Suspicion.NO_INTERNET,
        repairs.Suspicion.DNS_BROKEN,
    ):
        coord._apply_repair(suspicion)

    assert "missing:eth0" in calls
    assert "link:eth0:True" in calls
    assert any(call.startswith("ipv4:eth0:True") for call in calls)
    assert "route:True" in calls
