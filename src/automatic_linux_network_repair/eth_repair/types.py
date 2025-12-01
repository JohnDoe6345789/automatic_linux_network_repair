"""Shared dataclasses and enums for Ethernet repair helpers."""

from __future__ import annotations

import dataclasses
import enum
from typing import Dict, List, Tuple


@dataclasses.dataclass
class CommandResult:
    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str


class Suspicion(enum.Enum):
    INTERFACE_MISSING = "interface_missing"
    LINK_DOWN = "link_down"
    NO_IPV4 = "no_ipv4"
    NO_ROUTE = "no_route"
    NO_INTERNET = "no_internet"
    DNS_BROKEN = "dns_broken"


SUSPICION_LABELS: Dict[Suspicion, str] = {
    Suspicion.INTERFACE_MISSING: "Interface missing",
    Suspicion.LINK_DOWN: "Link down",
    Suspicion.NO_IPV4: "No IPv4 address",
    Suspicion.NO_ROUTE: "No default route",
    Suspicion.NO_INTERNET: "No internet (ICMP)",
    Suspicion.DNS_BROKEN: "DNS resolution failing",
}


@dataclasses.dataclass
class Diagnosis:
    suspicion_scores: Dict[Suspicion, float]

    def sorted_scores(self) -> List[Tuple[Suspicion, float]]:
        return sorted(
            self.suspicion_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )


class ResolvConfMode(enum.Enum):
    SYSTEMD_STUB = "systemd_stub"
    SYSTEMD_FULL = "systemd_full"
    MANUAL = "manual"
    OTHER = "other"
