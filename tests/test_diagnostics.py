"""Tests for fuzzy network diagnosis scoring logic."""

from automatic_linux_network_repair.eth_repair import diagnostics
from automatic_linux_network_repair.eth_repair.types import Diagnosis, ResolvConfMode, Suspicion


class _SilentLogger:
    def debug(self, *args, **kwargs):  # pragma: no cover - trivial stub
        return None


def test_fuzzy_diagnose_interface_missing(monkeypatch):
    """Interface absence should return an immediate INTERFACE_MISSING diagnosis."""

    monkeypatch.setattr(diagnostics, "DEFAULT_LOGGER", _SilentLogger())
    monkeypatch.setattr(diagnostics, "interface_exists", lambda iface: False)

    diag = diagnostics.fuzzy_diagnose("eth0")

    assert isinstance(diag, Diagnosis)
    assert diag.suspicion_scores[Suspicion.INTERFACE_MISSING] == 1.0
    # Other suspicions should remain at the default zero score when interface is missing.
    assert all(
        score == 0.0
        for suspicion, score in diag.suspicion_scores.items()
        if suspicion is not Suspicion.INTERFACE_MISSING
    )


def test_fuzzy_diagnose_dns_prioritized_when_systemd_stub_inactive(monkeypatch):
    """DNS issues should be escalated when systemd stub is configured but inactive."""

    monkeypatch.setattr(diagnostics, "DEFAULT_LOGGER", _SilentLogger())
    monkeypatch.setattr(diagnostics, "interface_exists", lambda iface: True)
    monkeypatch.setattr(diagnostics, "interface_link_up", lambda iface: True)
    monkeypatch.setattr(diagnostics, "interface_has_ipv4", lambda iface: True)
    monkeypatch.setattr(diagnostics, "has_default_route", lambda: True)
    monkeypatch.setattr(diagnostics, "ping_host", lambda host: True)
    monkeypatch.setattr(diagnostics, "dns_resolves", lambda name="deb.debian.org": False)
    monkeypatch.setattr(
        diagnostics,
        "systemd_resolved_status",
        lambda: {"active": False, "enabled": True},
    )
    monkeypatch.setattr(
        diagnostics,
        "detect_resolv_conf_mode",
        lambda: (ResolvConfMode.SYSTEMD_STUB, "/run/systemd/resolve/stub-resolv.conf"),
    )

    diag = diagnostics.fuzzy_diagnose("eth0")

    assert diag.suspicion_scores[Suspicion.DNS_BROKEN] == 1.0
    assert diag.top_suspicion is Suspicion.DNS_BROKEN
    # Non-DNS issues should not be raised when basic connectivity probes succeed.
    for suspicion in (
        Suspicion.INTERFACE_MISSING,
        Suspicion.LINK_DOWN,
        Suspicion.NO_IPV4,
        Suspicion.NO_ROUTE,
        Suspicion.NO_INTERNET,
    ):
        assert diag.suspicion_scores[suspicion] == 0.0
