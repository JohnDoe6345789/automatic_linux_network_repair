"""Tests for menu side effects and control flow wiring."""

import io

from automatic_linux_network_repair.eth_repair import menus
from tests.helpers import RecordingLogger


def test_side_effects_render_main_menu_and_capture_input():
    outputs = io.StringIO()
    choices = iter(["5"])
    effects = menus.EthernetMenuSideEffects(
        logger=RecordingLogger(),
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    choice = effects.show_main_menu("eth0")

    assert choice == "5"
    text = outputs.getvalue()
    assert "Ethernet repair menu" in text
    assert "Current interface: eth0" in text


def test_menu_handles_invalid_choice_and_exit(monkeypatch):
    logs = RecordingLogger()
    outputs = io.StringIO()
    choices = iter(["11", "10"])
    effects = menus.EthernetMenuSideEffects(
        logger=logs,
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    menu = menus.EthernetRepairMenu("eth0", False, effects)
    menu.run()

    assert any("Exiting menu" in msg for msg in logs.messages)
    assert "Invalid choice" in outputs.getvalue()


def test_menu_logs_advanced_menu_exit(monkeypatch):
    logs = RecordingLogger()
    outputs = io.StringIO()
    choices = iter(["9", "7", "10"])
    effects = menus.EthernetMenuSideEffects(
        logger=logs,
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    menu = menus.EthernetRepairMenu("eth0", False, effects)

    monkeypatch.setattr(menus, "show_systemd_dns_status", lambda: None)
    monkeypatch.setattr(menus, "set_systemd_resolved_enabled", lambda enabled, dry_run: None)
    monkeypatch.setattr(menus, "set_resolv_conf_symlink", lambda path, dry_run: None)
    monkeypatch.setattr(menus, "set_resolv_conf_manual_public", lambda dry_run: None)

    menu.run()

    assert any("Leaving advanced" in msg for msg in logs.messages)
    assert any("Exiting menu" in msg for msg in logs.messages)


def test_main_menu_lists_all_options():
    outputs = io.StringIO()
    choices = iter(["10"])
    effects = menus.EthernetMenuSideEffects(
        logger=RecordingLogger(),
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    menu = menus.EthernetRepairMenu("eth0", False, effects)
    menu.run()

    rendered = outputs.getvalue()
    for option_text in [
        "1) Show interface & connectivity status",
        "2) Run FULL fuzzy auto-diagnose & repair",
        "3) Bring link UP on current interface",
        "4) Obtain IPv4 / renew DHCP on interface",
        "5) Restart network stack (routing / services)",
        "6) Attempt DNS repair (may edit resolv.conf)",
        "7) Change interface",
        "8) Show ALL adapters & addresses",
        "9) Advanced systemd / DNS controls",
        "10) Quit",
    ]:
        assert option_text in rendered


def test_main_menu_rerenders_after_repair(monkeypatch):
    """After performing a repair action, the main menu should render again."""

    outputs = io.StringIO()
    choices = iter(["3", "10"])

    class RecordingEffects(menus.EthernetMenuSideEffects):
        def __init__(self):
            super().__init__(logger=RecordingLogger(), stdout=outputs, input_func=lambda prompt: next(choices))
            self.menu_calls: list[str] = []

        def show_main_menu(self, current_iface: str) -> str:  # type: ignore[override]
            self.menu_calls.append(current_iface)
            return super().show_main_menu(current_iface)

    effects = RecordingEffects()
    monkeypatch.setattr(menus, "repair_link_down", lambda iface, dry_run: None)
    monkeypatch.setattr(menus, "show_status", lambda iface: None)

    menu = menus.EthernetRepairMenu("eth0", False, effects)
    menu.run()

    assert effects.menu_calls == ["eth0", "eth0"]


def test_interface_change_updates_menu(monkeypatch):
    outputs = io.StringIO()
    choices = iter(["7", "eth1", "10"])
    effects = menus.EthernetMenuSideEffects(
        logger=RecordingLogger(),
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    monkeypatch.setattr(menus, "list_candidate_interfaces", lambda: ["eth0", "eth1"])
    monkeypatch.setattr(menus, "show_status", lambda iface: None)

    menu = menus.EthernetRepairMenu("eth0", False, effects)
    menu.run()

    rendered = outputs.getvalue()
    assert "Current interface: eth0" in rendered
    assert "Current interface: eth1" in rendered
