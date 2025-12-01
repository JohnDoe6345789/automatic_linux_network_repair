"""Tests for menu side effects and control flow wiring."""

import io

from automatic_linux_network_repair.eth_repair import menus
from tests.helpers import RecordingLogger


def test_side_effects_render_main_menu_and_capture_input():
    outputs = io.StringIO()
    choices = iter(['5'])
    effects = menus.EthernetMenuSideEffects(
        logger=RecordingLogger(),
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    choice = effects.show_main_menu('eth0')

    assert choice == '5'
    text = outputs.getvalue()
    assert 'Ethernet repair menu' in text
    assert 'Current interface: eth0' in text


def test_menu_handles_invalid_choice_and_exit(monkeypatch):
    logs = RecordingLogger()
    outputs = io.StringIO()
    choices = iter(['11', '10'])
    effects = menus.EthernetMenuSideEffects(
        logger=logs,
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    menu = menus.EthernetRepairMenu('eth0', False, effects)
    menu.run()

    assert any('Exiting menu' in msg for msg in logs.messages)
    assert 'Invalid choice' in outputs.getvalue()


def test_menu_logs_advanced_menu_exit(monkeypatch):
    logs = RecordingLogger()
    outputs = io.StringIO()
    choices = iter(['9', '7', '10'])
    effects = menus.EthernetMenuSideEffects(
        logger=logs,
        stdout=outputs,
        input_func=lambda prompt: next(choices),
    )

    menu = menus.EthernetRepairMenu('eth0', False, effects)

    monkeypatch.setattr(menus, 'show_systemd_dns_status', lambda: None)
    monkeypatch.setattr(menus, 'set_systemd_resolved_enabled', lambda enabled, dry_run: None)
    monkeypatch.setattr(menus, 'set_resolv_conf_symlink', lambda path, dry_run: None)
    monkeypatch.setattr(menus, 'set_resolv_conf_manual_public', lambda dry_run: None)

    menu.run()

    assert any('Leaving advanced' in msg for msg in logs.messages)
    assert any('Exiting menu' in msg for msg in logs.messages)
