import argparse
import asyncio
import logging

from github_service.__main__ import GithubServiceConfig
from github_service.__main__ import main as github_service_main
from github_service.service import CommitTestStatus, format_commit_status_description
from robot.__main__ import RobotArguments
from shared.utils import load_env_file


async def main():
    env = load_env_file()
    assert env.get("GITHUB_PAT") is not None, "GITHUB_PAT not found in environment"
    assert env.get("VRT_API_URL") is not None, "VRT_API_URL not found in environment"
    assert (
        env.get("VRT_ADMIN_API_KEY") is not None
    ), "VRT_ADMIN_API_KEY not found in environment"
    assert (
        env.get("VRT_ADMIN_EMAIL") is not None
    ), "VRT_ADMIN_EMAIL not found in environment"
    assert (
        env.get("VRT_ADMIN_PASSWORD") is not None
    ), "VRT_ADMIN_PASSWORD not found in environment"
    assert (
        env.get("VRT_FRONTEND_URL") is not None
    ), "VRT_FRONTEND_URL not found in environment"

    robot_args = RobotArguments(
        binary_path=env.get("BINARY_PATH"),
    )
    github_service_args = GithubServiceConfig(
        github_pat=env["GITHUB_PAT"],
        robot_args=robot_args,
        single_run_commit=env.get("SINGLE_RUN_COMMIT"),
        single_run_force_robot=env.get("SINGLE_RUN_FORCE_ROBOT"),
        vrt_api_url=env.get("VRT_API_URL"),
        vrt_api_key=env.get("VRT_ADMIN_API_KEY"),
        vrt_frontend_url=env.get("VRT_FRONTEND_URL"),
        vrt_email=env.get("VRT_ADMIN_EMAIL"),
        vrt_password=env.get("VRT_ADMIN_PASSWORD"),
    )
    await github_service_main(github_service_args)


# utility to reset commit status
def reset_commit(commit_hash: str):
    import github

    env = load_env_file()
    repo = github.Github(auth=github.Auth.Token(env["GITHUB_PAT"])).get_repo(
        "Cynteract/cynteract-app"
    )
    logging.info(f"Reset commit status for {commit_hash}.")
    commit = repo.get_commit(commit_hash)
    commit.create_status(
        state="pending",
        context="visual regression test",
        # description=f"[robot_pending] Manual reset",
        description=format_commit_status_description(
            CommitTestStatus.ROBOT_PENDING, "Manual reset"
        ),
    )


# utility to skip robot test for a commit
def skip_commit(commit_hash: str):
    import github

    env = load_env_file()
    repo = github.Github(auth=github.Auth.Token(env["GITHUB_PAT"])).get_repo(
        "Cynteract/cynteract-app"
    )
    logging.info(f"Skip robot test for commit {commit_hash}.")
    commit = repo.get_commit(commit_hash)
    commit.create_status(
        state="success",
        context="visual regression test",
        description=format_commit_status_description(
            CommitTestStatus.ROBOT_SKIPPED, "Manual skip"
        ),
    )


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(message)s", level=logging.INFO)

    env = load_env_file()

    argparser = argparse.ArgumentParser()
    argparser.add_argument(
        "--reset-commit",
        type=str,
        required=False,
        default=env.get("SINGLE_RUN_COMMIT"),
        help="Commit hash to reset.",
    )
    argparser.add_argument(
        "--skip-commit",
        type=str,
        required=False,
        default=env.get("SINGLE_RUN_COMMIT"),
        help="Commit hash to skip.",
    )
    args = argparser.parse_args()

    if args.reset_commit is not None:
        reset_commit(args.reset_commit)
    elif args.skip_commit is not None:
        skip_commit(args.skip_commit)
    else:
        asyncio.run(main())
