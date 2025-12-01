"""Tests for shell helpers and logging utilities."""

import logging

from automatic_linux_network_repair.eth_repair import logging_utils, shell


def test_cmd_str_quotes_arguments():
    """cmd_str should shell-escape each argument for readability."""

    runner = shell.ShellRunner(logger=logging_utils.LoggingManager("test_logger"))
    rendered = runner.cmd_str(["echo", "hello world", "special&chars"])

    assert rendered == "echo 'hello world' 'special&chars'"


def test_logging_manager_sets_level():
    """setup should configure the logger with the requested verbosity."""

    manager = logging_utils.LoggingManager("level_test")

    manager.setup(verbose=False)
    assert manager.logger.level == logging.INFO

    manager.setup(verbose=True)
    assert manager.logger.level == logging.DEBUG
