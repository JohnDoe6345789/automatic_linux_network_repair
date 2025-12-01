"""Shared dataclasses and enums for Ethernet repair helpers."""

from __future__ import annotations

import dataclasses
import enum


@dataclasses.dataclass
class CommandResult:
    cmd: list[str]
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


SUSPICION_LABELS: dict[Suspicion, str] = {
    Suspicion.INTERFACE_MISSING: "Interface missing",
    Suspicion.LINK_DOWN: "Link down",
    Suspicion.NO_IPV4: "No IPv4 address",
    Suspicion.NO_ROUTE: "No default route",
    Suspicion.NO_INTERNET: "No internet (ICMP)",
    Suspicion.DNS_BROKEN: "DNS resolution failing",
}


@dataclasses.dataclass
class Diagnosis:
    """Capture the results of a fuzzy connectivity diagnosis."""

    iface: str
    suspicion_scores: dict[Suspicion, float]

    def sorted_scores(self) -> list[tuple[Suspicion, float]]:
        """Return suspicion scores ordered by severity (highest first)."""
        return sorted(
            self.suspicion_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

    @property
    def top_suspicion(self) -> Suspicion:
        """Convenience accessor for the most likely root cause."""
        ordered = self.sorted_scores()
        return ordered[0][0] if ordered else Suspicion.NO_INTERNET


class ResolvConfMode(enum.Enum):
    SYSTEMD_STUB = "systemd_stub"
    SYSTEMD_FULL = "systemd_full"
    MANUAL = "manual"
    OTHER = "other"
