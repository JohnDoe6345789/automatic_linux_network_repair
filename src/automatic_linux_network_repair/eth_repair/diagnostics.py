"""Diagnosis helpers for fuzzy network issue scoring."""

from __future__ import annotations

from automatic_linux_network_repair.eth_repair.dns_config import (
    detect_resolv_conf_mode,
    systemd_resolved_status,
)
from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
from automatic_linux_network_repair.eth_repair.probes import (
    dns_resolves,
    has_default_route,
    interface_exists,
    interface_has_ipv4,
    interface_link_up,
    ping_host,
)
from automatic_linux_network_repair.eth_repair.types import Diagnosis, ResolvConfMode, Suspicion


def fuzzy_diagnose(iface: str) -> Diagnosis:
    scores: dict[Suspicion, float] = {
        Suspicion.INTERFACE_MISSING: 0.0,
        Suspicion.LINK_DOWN: 0.0,
        Suspicion.NO_IPV4: 0.0,
        Suspicion.NO_ROUTE: 0.0,
        Suspicion.NO_INTERNET: 0.0,
        Suspicion.DNS_BROKEN: 0.0,
    }

    exists = interface_exists(iface)
    link_up = interface_link_up(iface) if exists else False
    has_ip = interface_has_ipv4(iface) if exists else False
    default_route = has_default_route()
    can_ping_ip = ping_host("8.8.8.8")
    can_resolve = dns_resolves()

    sd_status = systemd_resolved_status()
    rc_mode, rc_detail = detect_resolv_conf_mode()

    DEFAULT_LOGGER.debug(
        "Diag raw: exists=%s link_up=%s has_ip=%s default_route=%s "
        "ping_ip=%s dns=%s sd_active=%s sd_enabled=%s rc_mode=%s rc_detail=%s",
        exists,
        link_up,
        has_ip,
        default_route,
        can_ping_ip,
        can_resolve,
        sd_status["active"],
        sd_status["enabled"],
        rc_mode.value,
        rc_detail,
    )

    if not exists:
        scores[Suspicion.INTERFACE_MISSING] = 1.0
        return Diagnosis(iface, scores)

    if not link_up:
        scores[Suspicion.LINK_DOWN] = 0.8

    if not has_ip:
        scores[Suspicion.NO_IPV4] = 0.7

    if not default_route:
        scores[Suspicion.NO_ROUTE] = 0.6

    if not can_ping_ip:
        scores[Suspicion.NO_INTERNET] = 0.6

    if can_ping_ip and not can_resolve:
        scores[Suspicion.DNS_BROKEN] = 0.9
    elif not can_resolve:
        scores[Suspicion.DNS_BROKEN] = 0.4

    dns_score = scores[Suspicion.DNS_BROKEN]
    if dns_score > 0.0:
        if rc_mode == ResolvConfMode.SYSTEMD_STUB and not sd_status["active"]:
            dns_score = max(dns_score, 1.0)
        elif rc_mode == ResolvConfMode.MANUAL and sd_status["active"]:
            dns_score = max(dns_score, 0.95)
        elif rc_mode in (ResolvConfMode.SYSTEMD_STUB, ResolvConfMode.SYSTEMD_FULL):
            dns_score = max(dns_score, 0.8)

        scores[Suspicion.DNS_BROKEN] = dns_score

    return Diagnosis(iface, scores)
