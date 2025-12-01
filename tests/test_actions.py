"""Tests for applying actions through the shell runner."""

from automatic_linux_network_repair.eth_repair import actions
from automatic_linux_network_repair.eth_repair.types import CommandResult


class _RecordingShell:
    def __init__(self, returncode: int = 0):
        self.returncode = returncode
        self.calls: list[list[str]] = []

    def cmd_str(self, cmd: list[str]) -> str:  # pragma: no cover - trivial passthrough
        return " ".join(cmd)

    def run_cmd(self, cmd: list[str], timeout: int = 5) -> CommandResult:  # noqa: ARG002
        self.calls.append(cmd)
        return CommandResult(cmd=cmd, returncode=self.returncode, stdout="", stderr="err")


class _NullLogger:
    def log(self, msg: str) -> None:  # pragma: no cover - noop for tests
        self.last = msg

    def debug(self, msg: str) -> None:  # pragma: no cover - noop for tests
        self.last = msg


def test_apply_action_respects_dry_run(monkeypatch):
    """Dry-run mode should skip shell execution but still log the action."""

    fake_shell = _RecordingShell()
    monkeypatch.setattr(actions, "DEFAULT_SHELL", fake_shell)
    monkeypatch.setattr(actions, "DEFAULT_LOGGER", _NullLogger())

    result = actions.apply_action("do nothing", ["echo", "hi"], dry_run=True)

    assert result is True
    assert fake_shell.calls == []


def test_apply_action_propagates_failure(monkeypatch):
    """Non-zero return codes should be reported as failure."""

    fake_shell = _RecordingShell(returncode=1)
    monkeypatch.setattr(actions, "DEFAULT_SHELL", fake_shell)
    monkeypatch.setattr(actions, "DEFAULT_LOGGER", _NullLogger())

    result = actions.apply_action("fail", ["false"], dry_run=False)

    assert result is False
    assert fake_shell.calls == [["false"]]
