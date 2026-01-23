import asyncio

from github_service.service import Service

# from pathlib import Path

# from test_runner.app import App
# from test_runner.tests import login


# async def main():
#     app_path = Path("C:/Program Files/Cynteract App/Cynteract.exe")
#     app = App(app_path)
#     state = await app.open()
#     app.resize(800, 600)
#     app.enforce_size()
#     if state == App.State.Launching:
#         # wait for app to finish launching
#         await asyncio.sleep(10)

#     await login.runTest()


async def main():
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            key, value = line.strip().split("=", 1)
            env[key] = value

    service = Service(env)
    # await service.run()
    await service.process_commit("f7a3782")


if __name__ == "__main__":
    asyncio.run(main())
