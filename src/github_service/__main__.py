import argparse
import asyncio
import logging

from github_service.service import GithubServiceConfig, Service
from robot.__main__ import RobotArguments
from setup.__main__ import load_env_file


async def main(args: GithubServiceConfig):
    service = Service(config=args)
    if args.single_run_commit:
        await service.process_commit(args.single_run_commit, force_run=True)
    else:
        logging.info(f"Start processing commits.")
        await service.run()


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(message)s", level=logging.INFO)

    env = load_env_file()
    github_pat = env.get("GITHUB_PAT")
    assert github_pat is not None, "GITHUB_PAT must be provided in .env file"

    parser = argparse.ArgumentParser(description="GitHub Service for Visual Testing.")
    parser.add_argument(
        "--single-run-commit",
        type=str,
        required=False,
        default=env.get("SINGLE_RUN_COMMIT"),
        help="If provided, only process this single commit SHA.",
    )
    args = parser.parse_args()
    robot_args = RobotArguments(
        binary_path=None,
    )
    github_service_args = GithubServiceConfig(
        github_pat=github_pat,
        robot_args=robot_args,
        single_run_commit=args.single_run_commit,
        vrt_api_url=env.get("VRT_API_URL"),
        vrt_api_key=env.get("VRT_ADMIN_API_KEY"),
        vrt_frontend_url=env.get("VRT_FRONTEND_URL"),
        vrt_email=env.get("VRT_ADMIN_EMAIL"),
        vrt_password=env.get("VRT_ADMIN_PASSWORD"),
    )
    asyncio.run(main(github_service_args))
