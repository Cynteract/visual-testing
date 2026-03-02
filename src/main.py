import argparse
import asyncio
import logging

from github_service.__main__ import GithubServiceConfig
from github_service.__main__ import main as github_service_main
from github_service.service import CommitTestStatus, format_commit_status_description
from robot.__main__ import RobotArguments
from shared.utils import load_env_file

logging.basicConfig(level=logging.INFO)


async def main():
    env = load_env_file()
    assert env.get("GITHUB_PAT") is not None, "GITHUB_PAT not found in environment"
    assert env.get("USERNAME") is not None, "USERNAME not found in environment"
    assert env.get("PASSWORD") is not None, "PASSWORD not found in environment"
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
        username=env["USERNAME"],
        password=env["PASSWORD"],
        binary_path=env.get("BINARY_PATH"),
    )
    github_service_args = GithubServiceConfig(
        github_pat=env["GITHUB_PAT"],
        robot_args=robot_args,
        single_run_commit=env.get("SINGLE_RUN_COMMIT"),
        vrt_api_url=env.get("VRT_API_URL"),
        vrt_api_key=env.get("VRT_ADMIN_API_KEY"),
        vrt_frontend_url=env.get("VRT_FRONTEND_URL"),
        vrt_email=env.get("VRT_ADMIN_EMAIL"),
        vrt_password=env.get("VRT_ADMIN_PASSWORD"),
    )
    await github_service_main(github_service_args)


# utility to reset commit status
def reset_commit():
    import github

    env = load_env_file()
    repo = github.Github(auth=github.Auth.Token(env["GITHUB_PAT"])).get_repo(
        "Cynteract/cynteract-app"
    )
    logging.info(f"Reset commit status for {env['SINGLE_RUN_COMMIT']}.")
    commit = repo.get_commit(env["SINGLE_RUN_COMMIT"])
    commit.create_status(
        state="pending",
        context="visual regression test",
        # description=f"[robot_pending] Manual reset",
        description=format_commit_status_description(
            CommitTestStatus.ROBOT_PENDING, "Manual reset"
        ),
    )


# utility to skip robot test for a commit
def skip_commit():
    import github

    env = load_env_file()
    repo = github.Github(auth=github.Auth.Token(env["GITHUB_PAT"])).get_repo(
        "Cynteract/cynteract-app"
    )
    logging.info(f"Skip robot test for commit {env['SINGLE_RUN_COMMIT']}.")
    commit = repo.get_commit(env["SINGLE_RUN_COMMIT"])
    commit.create_status(
        state="success",
        context="visual regression test",
        description=format_commit_status_description(
            CommitTestStatus.ROBOT_SKIPPED, "Manual skip"
        ),
    )


if __name__ == "__main__":
    # arguments --reset-commit
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--reset-commit", action="store_true")
    argparser.add_argument("--skip-commit", action="store_true")
    args = argparser.parse_args()
    if args.reset_commit:
        reset_commit()
    elif args.skip_commit:
        skip_commit()
    else:
        asyncio.run(main())
