import asyncio
from pathlib import Path

from test_runner.app import App
from test_runner.tests import login


async def main():
    app_path = Path("C:/Program Files/Cynteract App/Cynteract.exe")
    app = App(app_path)
    state = await app.open()
    app.resize(800, 600)
    app.enforce_size()
    if state == App.State.Launching:
        # wait for app to finish launching
        await asyncio.sleep(10)

    await login.runTest()


if __name__ == "__main__":
    asyncio.run(main())
