import time


class Timeout:
    def __init__(self, timeout: float, error_message: str):
        self.timeout = timeout
        self.error_message = error_message
        self.start_time = time.time()

    def check(self):
        if time.time() - self.start_time > self.timeout:
            raise TimeoutError(self.error_message)
