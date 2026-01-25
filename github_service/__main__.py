import argparse
import asyncio

from github_service.service import GithubServiceConfig, Service
from test_runner.__main__ import TestRunnerArguments


async def main(args: GithubServiceConfig):
    service = Service(config=args)
    if args.single_run_commit:
        await service.process_commit(args.single_run_commit)
    else:
        await service.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Service for Visual Testing.")
    parser.add_argument(
        "--github-pat", type=str, required=True, help="GitHub Personal Access Token."
    )
    parser.add_argument(
        "--username", type=str, required=True, help="Username for test runner."
    )
    parser.add_argument(
        "--password", type=str, required=True, help="Password for test runner."
    )
    parser.add_argument(
        "--single-run-commit",
        type=str,
        required=False,
        help="If provided, only process this single commit SHA.",
    )
    parser.add_argument(
        "--vrt-apiurl",
        type=str,
        required=False,
        help="VRT API URL.",
    )
    parser.add_argument(
        "--vrt-apikey",
        type=str,
        required=False,
        help="VRT API Key.",
    )
    parser.add_argument(
        "--vrt-frontendurl",
        type=str,
        required=False,
        help="VRT Frontend URL.",
    )
    args = parser.parse_args()
    test_runner_args = TestRunnerArguments(
        binary_path=None,
        username=args.username,
        password=args.password,
    )
    github_service_args = GithubServiceConfig(
        github_pat=args.github_pat,
        test_runner_args=test_runner_args,
        single_run_commit=args.single_run_commit,
        vrt_api_url=args.vrt_apiurl,
        vrt_api_key=args.vrt_apikey,
        vrt_frontend_url=args.vrt_frontendurl,
    )
    asyncio.run(main(github_service_args))
