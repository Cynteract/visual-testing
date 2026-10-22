"""Structured failure classification shared by the runner and PR service."""

import json
import logging
import shutil
from pathlib import Path

import pytest


class LoginTransitionTimeout(TimeoutError):
    """Login was submitted, but the application did not leave the login page."""


class RobotFailure(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class AttemptEvidence:
    def __init__(self, directory: Path):
        self.directory = directory
        self.failures = []

    def pytest_runtest_makereport(self, item, call):
        if call.excinfo is not None and not isinstance(call.excinfo.value, pytest.skip.Exception):
            error = call.excinfo.value
            self.failures.append({
                "test": item.nodeid,
                "phase": call.when,
                "type": type(error).__name__,
                "message": str(error),
                "duration_seconds": call.duration,
                "retryable": True,
            })

    def save(self, exit_code):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "result.json").write_text(
            json.dumps({"exit_code": int(exit_code), "failures": self.failures}, indent=2),
            encoding="utf-8",
        )
        source = Path.home() / "AppData/LocalLow/Cynteract/Cynteract/Player.log"
        try:
            if source.exists():
                shutil.copy2(source, self.directory / "Player.log")
        except OSError:
            logging.exception("Could not preserve application log")

    @property
    def retryable(self):
        return bool(self.failures) and all(f["retryable"] for f in self.failures)
