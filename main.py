import asyncio

from github_service.__main__ import GithubServiceArguments
from github_service.__main__ import main as github_service_main
from test_runner.__main__ import TestRunnerArguments
from test_runner.__main__ import main as test_runner_main


async def main():
    # Load .env file
    env = {}
    with open(".env") as f:
        for line in f:
            key, value = line.strip().split("=", 1)
            env[key] = value

    assert env.get("GITHUB_PAT") is not None, "GITHUB_PAT not found in environment"
    assert env.get("USERNAME") is not None, "USERNAME not found in environment"
    assert env.get("PASSWORD") is not None, "PASSWORD not found in environment"
    assert env.get("VRT_APIURL") is not None, "VRT_APIURL not found in environment"
    assert env.get("VRT_APIKEY") is not None, "VRT_APIKEY not found in environment"
    assert (
        env.get("VRT_FRONTENDURL") is not None
    ), "VRT_FRONTENDURL not found in environment"

    test_runner_args = TestRunnerArguments(
        username=env["USERNAME"],
        password=env["PASSWORD"],
        binary_path=env.get("BINARY_PATH"),
    )
    github_service_args = GithubServiceArguments(
        github_pat=env["GITHUB_PAT"],
        test_runner_args=test_runner_args,
        single_run_commit=env.get("SINGLE_RUN_COMMIT"),
        vrt_api_url=env.get("VRT_APIURL"),
        vrt_api_key=env.get("VRT_APIKEY"),
        vrt_frontend_url=env.get("VRT_FRONTENDURL"),
    )
    # to configure for debugging, change the number below
    match 1:
        case 0:
            await test_runner_main(test_runner_args)
        case 1:
            await github_service_main(github_service_args)


if __name__ == "__main__":
    asyncio.run(main())
