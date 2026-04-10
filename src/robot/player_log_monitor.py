import asyncio
from pathlib import Path

from robot.timeout import Timeout


class PlayerLogMonitor:
    class _AssertNewLogEntry:
        def __init__(
            self, log_file_path: Path, expected_entry: str, timeout: float | None = None
        ):
            self.log_file_path = log_file_path
            self.last_position = 0
            self.expected_entry = expected_entry
            self.timeout = timeout if timeout is not None else 1.0

        async def __aenter__(self):
            # move to the end of the file
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                f.seek(0, 2)
                self.last_position = f.tell()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            timer = Timeout(
                self.timeout,
                f"Expected log entry '{self.expected_entry}' not found within {self.timeout} seconds",
            )
            with open(self.log_file_path, "r", encoding="utf-8") as f:
                f.seek(self.last_position)
                new_content = f.read()
                if self.expected_entry in new_content:
                    return
                timer.check()
                await asyncio.sleep(0.5)

    def __init__(self):
        self.log_file_path = (
            Path.home() / "AppData/LocalLow/Cynteract/Cynteract/Player.log"
        )

    def assert_line(
        self, expected_entry: str, timeout: float | None = None
    ) -> _AssertNewLogEntry:
        return self._AssertNewLogEntry(self.log_file_path, expected_entry, timeout)
