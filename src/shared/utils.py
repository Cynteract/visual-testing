import logging
import os
import time


def load_env_file() -> dict[str, str]:
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                env[key] = value
                os.environ[key] = value
    return env


class PrintDuration:
    def __init__(self, message: str):
        self.message = message

    def __enter__(self):
        self.start_time = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        logging.warning(f"{self.message} duration: {duration:.3f}s")
