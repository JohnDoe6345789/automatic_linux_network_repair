"""Reusable test utilities and recording stubs for the test suite."""


class RecordingLogger:
    """In-memory logger capturing log messages and setup calls."""

    def __init__(self):
        self.messages: list[str] = []
        self.setup_calls: list[bool] = []

    def setup(self, verbose: bool) -> None:
        self.setup_calls.append(verbose)

    def log(self, msg: str) -> None:
        self.messages.append(msg)

    def debug(self, msg: str) -> None:  # pragma: no cover - simple passthrough
        self.messages.append(f"DEBUG:{msg}")
