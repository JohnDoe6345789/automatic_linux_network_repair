"""Wi-Fi helpers for scanning and connecting across common Linux backends."""

from __future__ import annotations

import dataclasses
import enum
import re
import shutil
from collections.abc import Iterable, Sequence

from automatic_linux_network_repair.eth_repair.logging_utils import LoggingManager
from automatic_linux_network_repair.eth_repair.shell import DEFAULT_SHELL, ShellRunner
from automatic_linux_network_repair.eth_repair.types import CommandResult


class SecurityType(enum.Enum):
    """Supported Wi-Fi security options."""

    OPEN = "open"
    WEP = "wep"
    WPA = "wpa"
    WPA2 = "wpa2"
    WPA3 = "wpa3"

    @classmethod
    def from_label(cls, value: str | None) -> SecurityType:
        """Convert user-provided security labels into enums."""

        if value is None:
            return cls.WPA2
        normalized = value.lower().replace("-", "")
        mapping = {
            "open": cls.OPEN,
            "none": cls.OPEN,
            "wep": cls.WEP,
            "wpa": cls.WPA,
            "wpa1": cls.WPA,
            "wpa2": cls.WPA2,
            "wpa3": cls.WPA3,
            "sae": cls.WPA3,
        }
        return mapping.get(normalized, cls.WPA2)


@dataclasses.dataclass
class WirelessNetwork:
    """Observed Wi-Fi network entry."""

    ssid: str
    bssid: str | None
    signal: int | None
    security: list[str]


@dataclasses.dataclass
class ConnectionResult:
    """Outcome from a connection attempt."""

    backend: str
    success: bool
    message: str


class WirelessBackend:
    """Abstract interface for scan/connect helpers."""

    name = "wireless"

    def __init__(self, *, shell: ShellRunner = DEFAULT_SHELL, logger: LoggingManager | None = None) -> None:
        self.shell = shell
        self.logger = logger or LoggingManager("wifi")

    def scan(self, interface: str) -> list[WirelessNetwork]:  # pragma: no cover - interface contract
        raise NotImplementedError

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None,
        security: SecurityType,
    ) -> ConnectionResult:  # pragma: no cover - interface contract
        raise NotImplementedError


class NmcliBackend(WirelessBackend):
    """NetworkManager-based Wi-Fi control via nmcli."""

    name = "nmcli"

    def scan(self, interface: str) -> list[WirelessNetwork]:
        cmd = [
            "nmcli",
            "-t",
            "-f",
            "BSSID,SSID,SECURITY,SIGNAL",
            "--separator",
            "|",
            "device",
            "wifi",
            "list",
            "ifname",
            interface,
        ]
        result = self.shell.run_cmd(cmd, timeout=20)
        if result.returncode != 0:
            self.logger.debug(f"nmcli scan failed: {result.stderr.strip()}")
            return []

        networks: list[WirelessNetwork] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("|")
            bssid, ssid, security, signal = (parts + [None, None, None, None])[:4]
            networks.append(
                WirelessNetwork(
                    ssid=ssid or "",
                    bssid=bssid or None,
                    signal=int(signal) if signal and signal.isdigit() else None,
                    security=[sec for sec in (security or "").split(" ") if sec],
                )
            )
        return networks

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None,
        security: SecurityType,
    ) -> ConnectionResult:
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "ifname", interface]
        if password:
            if security == SecurityType.WEP:
                cmd += ["wep-key0", password]
            else:
                cmd += ["password", password]
        res = self.shell.run_cmd(cmd, timeout=30)
        if res.returncode != 0:
            msg = res.stderr.strip() or "nmcli connection failed"
            self.logger.log(f"[WARN] nmcli failed to connect: {msg}")
            return ConnectionResult(self.name, False, msg)
        return ConnectionResult(self.name, True, res.stdout.strip() or "Connected")


class WpaCliBackend(WirelessBackend):
    """wpa_supplicant control via wpa_cli."""

    name = "wpa_cli"

    def _call(self, interface: str, *args: str, timeout: int = 10) -> CommandResult:
        cmd = ["wpa_cli", "-i", interface, *args]
        return self.shell.run_cmd(cmd, timeout=timeout)

    def scan(self, interface: str) -> list[WirelessNetwork]:
        self._call(interface, "scan", timeout=15)
        results = self._call(interface, "scan_results", timeout=15)
        if results.returncode != 0:
            self.logger.debug(f"wpa_cli scan failed: {results.stderr.strip()}")
            return []

        networks: list[WirelessNetwork] = []
        for line in results.stdout.splitlines()[1:]:
            # Format: bssid / freq / signal level / flags / ssid
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            bssid, _, signal, flags, ssid = parts[:5]
            networks.append(
                WirelessNetwork(
                    ssid=ssid,
                    bssid=bssid,
                    signal=int(signal) if signal.lstrip("-").isdigit() else None,
                    security=[flag.strip("[]") for flag in flags.split("[") if "]" in flag],
                )
            )
        return networks

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None,
        security: SecurityType,
    ) -> ConnectionResult:
        add_res = self._call(interface, "add_network")
        if add_res.returncode != 0:
            msg = add_res.stderr.strip() or "Failed to add network"
            return ConnectionResult(self.name, False, msg)
        network_id = add_res.stdout.strip().splitlines()[-1]

        commands: list[Sequence[str]] = [
            ("set_network", network_id, "ssid", f'"{ssid}"'),
            ("set_network", network_id, "scan_ssid", "1"),
        ]

        if security == SecurityType.OPEN:
            commands.append(("set_network", network_id, "key_mgmt", "NONE"))
        elif security == SecurityType.WEP:
            commands.extend(
                [
                    ("set_network", network_id, "key_mgmt", "NONE"),
                    ("set_network", network_id, "wep_key0", f'"{password or ""}"'),
                ]
            )
        else:
            psk = password or ""
            commands.append(("set_network", network_id, "psk", f'"{psk}"'))
            if security == SecurityType.WPA3:
                commands.append(("set_network", network_id, "key_mgmt", "SAE"))
            else:
                commands.append(("set_network", network_id, "key_mgmt", "WPA-PSK"))

        for cmd in commands:
            res = self._call(interface, *cmd)
            if res.returncode != 0:
                msg = res.stderr.strip() or "Failed to configure network"
                return ConnectionResult(self.name, False, msg)

        self._call(interface, "enable_network", network_id)
        sel_res = self._call(interface, "select_network", network_id, timeout=15)
        if sel_res.returncode != 0:
            msg = sel_res.stderr.strip() or "Failed to select network"
            return ConnectionResult(self.name, False, msg)

        return ConnectionResult(self.name, True, "Connected")


class IwctlBackend(WirelessBackend):
    """iwd control through iwctl."""

    name = "iwctl"

    def scan(self, interface: str) -> list[WirelessNetwork]:
        scan_res = self.shell.run_cmd(["iwctl", "station", interface, "scan"], timeout=15)
        if scan_res.returncode != 0:
            self.logger.debug(f"iwctl scan failed: {scan_res.stderr.strip()}")
            return []
        list_res = self.shell.run_cmd(["iwctl", "station", interface, "get-networks"], timeout=15)
        if list_res.returncode != 0:
            self.logger.debug(f"iwctl list failed: {list_res.stderr.strip()}")
            return []

        networks: list[WirelessNetwork] = []
        for line in list_res.stdout.splitlines():
            # Expected columns: Network name | Security | Signal | ...
            parts = [part for part in line.split() if part]
            if len(parts) < 3 or parts[0].lower() == "network":
                continue
            ssid, security, signal = parts[0], parts[1], parts[2]
            networks.append(
                WirelessNetwork(
                    ssid=ssid,
                    bssid=None,
                    signal=int(signal.replace("*", "")) if signal.strip("*").isdigit() else None,
                    security=[security],
                )
            )
        return networks

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None,
        security: SecurityType,
    ) -> ConnectionResult:
        cmd = ["iwctl", "station", interface, "connect", ssid]
        if password:
            cmd += ["-P", password]
        res = self.shell.run_cmd(cmd, timeout=30)
        if res.returncode != 0:
            msg = res.stderr.strip() or "iwctl connection failed"
            return ConnectionResult(self.name, False, msg)
        return ConnectionResult(self.name, True, "Connected")


class IwlistBackend(WirelessBackend):
    """Fallback scanning via iwlist and rudimentary iwconfig connection."""

    name = "iwlist"

    _essid_re = re.compile(r"ESSID:\"?(.*?)\"?$")
    _quality_re = re.compile(r"Quality=(\d+)/")
    _enc_re = re.compile(r"Encryption key:(on|off)")

    def scan(self, interface: str) -> list[WirelessNetwork]:
        res = self.shell.run_cmd(["iwlist", interface, "scanning"], timeout=20)
        if res.returncode != 0:
            self.logger.debug(f"iwlist scan failed: {res.stderr.strip()}")
            return []

        networks: list[WirelessNetwork] = []
        essid: str | None = None
        quality: int | None = None
        enc: list[str] = []
        for line in res.stdout.splitlines():
            if match := self._essid_re.search(line.strip()):
                if essid:
                    networks.append(
                        WirelessNetwork(
                            ssid=essid,
                            bssid=None,
                            signal=quality,
                            security=enc or ["open"],
                        )
                    )
                essid = match.group(1)
                quality = None
                enc = []
                continue
            if match := self._quality_re.search(line):
                try:
                    quality = int(match.group(1))
                except ValueError:
                    quality = None
            if match := self._enc_re.search(line):
                enc = ["wep"] if match.group(1) == "on" else ["open"]
        if essid:
            networks.append(
                WirelessNetwork(
                    ssid=essid,
                    bssid=None,
                    signal=quality,
                    security=enc or ["open"],
                )
            )
        return networks

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None,
        security: SecurityType,
    ) -> ConnectionResult:
        base_cmds: list[list[str]] = [["iwconfig", interface, "essid", ssid]]
        if security == SecurityType.WEP and password:
            base_cmds.append(["iwconfig", interface, "key", password])
        elif security != SecurityType.OPEN:
            return ConnectionResult(
                self.name,
                False,
                "Secure connection unsupported with iwconfig; try another backend",
            )

        for cmd in base_cmds:
            res = self.shell.run_cmd(cmd, timeout=15)
            if res.returncode != 0:
                msg = res.stderr.strip() or "iwconfig failed"
                return ConnectionResult(self.name, False, msg)
        return ConnectionResult(self.name, True, "Connected")


class WirelessManager:
    """Facade that selects available wireless backends and exposes simple APIs."""

    def __init__(
        self,
        *,
        shell: ShellRunner = DEFAULT_SHELL,
        logger: LoggingManager | None = None,
        backends: Iterable[WirelessBackend] | None = None,
    ) -> None:
        self.shell = shell
        self.logger = logger or LoggingManager("wifi_manager")
        self.backends = list(backends) if backends is not None else self._detect_backends()

    def detect_interface(self) -> str | None:
        """Heuristically determine a wireless interface name.

        The resolver prefers explicit wireless tooling (``iw`` or ``nmcli``) and
        falls back to parsing ``ip link`` output for commonly named interfaces.
        Returns ``None`` when no plausible wireless adapter is found.
        """

        interface = self._detect_with_iw()
        if interface:
            return interface

        interface = self._detect_with_nmcli()
        if interface:
            return interface

        return self._detect_with_ip_link()

    def _detect_backends(self) -> list[WirelessBackend]:
        ordered: list[tuple[str, type[WirelessBackend]]] = [
            ("nmcli", NmcliBackend),
            ("iwctl", IwctlBackend),
            ("wpa_cli", WpaCliBackend),
            ("iwlist", IwlistBackend),
        ]
        available: list[WirelessBackend] = []
        for binary, backend_cls in ordered:
            if shutil.which(binary):
                available.append(backend_cls(shell=self.shell, logger=self.logger))
        return available

    def _detect_with_iw(self) -> str | None:
        if not shutil.which("iw"):
            return None

        res = self.shell.run_cmd(["iw", "dev"], timeout=8)
        if res.returncode != 0:
            self.logger.debug(f"iw dev failed while detecting interface: {res.stderr.strip()}")
            return None

        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("Interface "):
                return line.split()[1]
        return None

    def _detect_with_nmcli(self) -> str | None:
        if not shutil.which("nmcli"):
            return None

        res = self.shell.run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE", "device", "status"], timeout=8)
        if res.returncode != 0:
            self.logger.debug(f"nmcli device status failed while detecting interface: {res.stderr.strip()}")
            return None

        for line in res.stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[1].strip() == "wifi" and parts[0].strip():
                return parts[0].strip()
        return None

    def _detect_with_ip_link(self) -> str | None:
        res = self.shell.run_cmd(["ip", "-o", "link", "show"], timeout=8)
        if res.returncode != 0:
            self.logger.debug(f"ip link show failed while detecting interface: {res.stderr.strip()}")
            return None

        for line in res.stdout.splitlines():
            parts = line.split(":", 2)
            if len(parts) < 2:
                continue
            name = parts[1].strip().split("@")[0]
            lowered = name.lower()
            if lowered.startswith(("wlan", "wlp", "wlx", "wifi", "wwan")):
                return name
        return None

    def scan(self, interface: str, preferred_backend: str | None = None) -> list[WirelessNetwork]:
        backend = self._choose_backend(preferred_backend)
        if backend is None:
            self.logger.log("[ERROR] No wireless backend available for scanning.")
            return []
        return backend.scan(interface)

    def connect(
        self,
        interface: str,
        ssid: str,
        password: str | None = None,
        security: SecurityType | str | None = None,
        preferred_backend: str | None = None,
    ) -> ConnectionResult:
        security_enum = security if isinstance(security, SecurityType) else SecurityType.from_label(security)
        for backend in self._candidate_backends(preferred_backend):
            result = backend.connect(interface, ssid, password, security_enum)
            if result.success:
                return result
            self.logger.debug(f"Backend {backend.name} failed to connect to {ssid!r}: {result.message}")
        return ConnectionResult("none", False, "No wireless backend could establish the connection")

    def _candidate_backends(self, preferred_backend: str | None) -> Iterable[WirelessBackend]:
        if preferred_backend:
            for backend in self.backends:
                if backend.name == preferred_backend:
                    yield backend
                    break
        for backend in self.backends:
            if preferred_backend and backend.name == preferred_backend:
                continue
            yield backend

    def _choose_backend(self, preferred_backend: str | None) -> WirelessBackend | None:
        for backend in self._candidate_backends(preferred_backend):
            return backend
        return None
