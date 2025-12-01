"""Status rendering helpers for Ethernet repair operations."""

from __future__ import annotations

from automatic_linux_network_repair.eth_repair.logging_utils import log
from automatic_linux_network_repair.eth_repair.probes import (
    detect_network_managers,
    dns_resolves,
    has_default_route,
    interface_exists,
    interface_ip_addrs,
    interface_link_up,
    list_all_interfaces_detailed,
    ping_host,
    read_resolv_conf_summary,
)


def show_status(iface: str) -> None:
    log("")
    log("=== Interface & connectivity status ===")
    exists = interface_exists(iface)
    link_up = interface_link_up(iface) if exists else False
    ipv4_addrs = interface_ip_addrs(iface, family=4) if exists else []
    ipv6_addrs = interface_ip_addrs(iface, family=6) if exists else []
    has_ip = bool(ipv4_addrs)
    default_route = has_default_route()
    ping_ip_ok = ping_host("8.8.8.8")
    dns_ok = dns_resolves()
    managers = detect_network_managers()

    log(f"Interface:           {iface}")
    log(f"Exists:              {exists}")
    log(f"Link up:             {link_up}")
    log(f"IPv4 addresses:      {', '.join(ipv4_addrs) or 'None'}")
    log(f"IPv6 addresses:      {', '.join(ipv6_addrs) or 'None'}")
    log(f"Has IPv4:            {has_ip}")
    log(f"Default route:       {default_route}")
    log(f"Ping 8.8.8.8:        {ping_ip_ok}")
    log(f"DNS deb.debian.org:  {dns_ok}")
    log("")
    log("Network managers:")
    for name, active in managers.items():
        log(f"  {name:17s}: {'active' if active else 'inactive'}")
    log("")
    log("/etc/resolv.conf (first lines):")
    for line in read_resolv_conf_summary():
        log(f"  {line}")
    log("=======================================")


def show_all_adapters() -> None:
    log("")
    log("=== All adapters & addresses (ip -br addr show) ===")
    for line in list_all_interfaces_detailed():
        log(f"  {line}")
    log("==================================================")
