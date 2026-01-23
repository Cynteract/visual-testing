import argparse
import asyncio
from dataclasses import dataclass

from github_service.service import Service
from test_runner.__main__ import TestRunnerArguments


@dataclass
class GithubServiceArguments:
    github_pat: str
    test_runner_args: TestRunnerArguments
    single_run_commit: str | None = None


async def main(args: GithubServiceArguments):
    service = Service(args.github_pat, args.test_runner_args)
    if args.single_run_commit is not None:
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
    args = parser.parse_args()
    test_runner_args = TestRunnerArguments(
        binary_path=None,
        username=args.username,
        password=args.password,
    )
    github_service_args = GithubServiceArguments(
        github_pat=args.github_pat,
        test_runner_args=test_runner_args,
        single_run_commit=args.single_run_commit,
    )
    asyncio.run(main(github_service_args))
