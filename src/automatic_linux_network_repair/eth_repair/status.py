"""Status rendering helpers for Ethernet repair operations."""

from __future__ import annotations

from automatic_linux_network_repair.eth_repair.logging_utils import DEFAULT_LOGGER
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
    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("=== Interface & connectivity status ===")
    exists = interface_exists(iface)
    link_up = interface_link_up(iface) if exists else False
    ipv4_addrs = interface_ip_addrs(iface, family=4) if exists else []
    ipv6_addrs = interface_ip_addrs(iface, family=6) if exists else []
    has_ip = bool(ipv4_addrs)
    default_route = has_default_route()
    ping_ip_ok = ping_host("8.8.8.8")
    dns_ok = dns_resolves()
    managers = detect_network_managers()

    DEFAULT_LOGGER.log(f"Interface:           {iface}")
    DEFAULT_LOGGER.log(f"Exists:              {exists}")
    DEFAULT_LOGGER.log(f"Link up:             {link_up}")
    DEFAULT_LOGGER.log(f"IPv4 addresses:      {', '.join(ipv4_addrs) or 'None'}")
    DEFAULT_LOGGER.log(f"IPv6 addresses:      {', '.join(ipv6_addrs) or 'None'}")
    DEFAULT_LOGGER.log(f"Has IPv4:            {has_ip}")
    DEFAULT_LOGGER.log(f"Default route:       {default_route}")
    DEFAULT_LOGGER.log(f"Ping 8.8.8.8:        {ping_ip_ok}")
    DEFAULT_LOGGER.log(f"DNS deb.debian.org:  {dns_ok}")
    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("Network managers:")
    for name, active in managers.items():
        DEFAULT_LOGGER.log(f"  {name:17s}: {'active' if active else 'inactive'}")
    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("/etc/resolv.conf (first lines):")
    for line in read_resolv_conf_summary():
        DEFAULT_LOGGER.log(f"  {line}")
    DEFAULT_LOGGER.log("=======================================")


def show_all_adapters() -> None:
    DEFAULT_LOGGER.log("")
    DEFAULT_LOGGER.log("=== All adapters & addresses (ip -br addr show) ===")
    for line in list_all_interfaces_detailed():
        DEFAULT_LOGGER.log(f"  {line}")
    DEFAULT_LOGGER.log("==================================================")
