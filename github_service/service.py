import asyncio
import base64
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import github
import requests
from github.Commit import Commit
from visual_regression_tracker import (
    Config,
    TestRun,
    TestRunError,
    VisualRegressionTracker,
)

from test_runner.__main__ import TestRunnerArguments, main
from test_runner.config import get_screenshot_dir


@dataclass
class GithubServiceConfig:
    github_pat: str
    test_runner_args: TestRunnerArguments
    single_run_commit: str | None = None
    vrt_api_url: str | None = None
    vrt_api_key: str | None = None
    vrt_frontend_url: str | None = None


class TestResult:
    def __init__(self, passed: bool, details: str, target_url: str | None = None):
        self.passed = passed
        self.details = details
        self.target_url = target_url


class Service:
    def __init__(
        self,
        config: GithubServiceConfig,
    ):
        self.config = config
        self.repo = github.Github(login_or_token=config.github_pat).get_repo(
            "Cynteract/cynteract-app"
        )

    async def execute_command(self, *args: str, **kwargs) -> str:
        print(f"Executing command: {' '.join(args)}")
        subprocess_result = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            **kwargs,
        )
        stdout, stderr = await subprocess_result.communicate()
        if subprocess_result.returncode != 0:
            raise RuntimeError(
                f"Command failed with code {subprocess_result.returncode}: {stderr.decode()}"
            )
        return stdout.decode().strip()

    async def get_version_info(self, *args: str) -> str:
        # needs the cynteract-app repo to be cloned locally
        app_dir = Path("../cynteract-app")
        if not app_dir.exists():
            # clone the repo with PAT
            clone_url = self.repo.clone_url.replace(
                "https://", f"https://{self.config.github_pat}@"
            )
            await self.execute_command("git", "clone", clone_url, app_dir.as_posix())
        else:
            # fetch the latest changes
            await self.execute_command("git", "fetch", "origin", cwd=app_dir.as_posix())
        version_info = await self.execute_command(
            sys.executable, "tools/get_version_info.py", *args, cwd=app_dir.as_posix()
        )
        return version_info

    async def upload_screenshots(self, file_name_base: str) -> tuple[bool, str | None]:
        auto_pass = True
        build_url = None
        if self.config.vrt_api_url and self.config.vrt_api_key:
            config = Config(
                apiUrl=self.config.vrt_api_url,
                apiKey=self.config.vrt_api_key,
                branchName="development",
                project="Cynteract app",
                ciBuildId=file_name_base,
            )
            with VisualRegressionTracker(config) as vrt:
                build_url = f"{self.config.vrt_frontend_url}/{vrt.projectId}?buildId={vrt.buildId}"
                screenshot_dir = get_screenshot_dir(file_name_base)
                for image_path in screenshot_dir.glob("*.png"):
                    try:
                        with image_path.open("rb") as f:
                            image_data = f.read()
                            vrt.track(
                                TestRun(
                                    name=image_path.stem,
                                    imageBase64=base64.b64encode(image_data).decode(
                                        "utf-8"
                                    ),
                                )
                            )
                    except TestRunError:
                        auto_pass = False
                        # continue with next image
                        pass
                    # yield
                    await asyncio.sleep(0)
        return auto_pass, build_url

    async def get_file_name_base(self, commit: Commit) -> str:
        if any(
            branch.name == "development" for branch in commit.get_branches_where_head()
        ):
            version_info = await self.get_version_info(
                "--ci-development", "--commitish=" + commit.sha
            )
        elif commit.get_pulls().totalCount > 0:
            pr_number = commit.get_pulls().get_page(0)[0].number
            version_info = await self.get_version_info(
                f"--ci-pr={pr_number}", "--commitish=" + commit.sha
            )
        else:
            raise RuntimeError(f"Neither development nor PR commit: {commit.sha}")
        _, file_name_base, _ = version_info.split(",")
        return file_name_base

    async def run_commit_test(self, file_name_base: str) -> TestResult:
        try:
            # run test-runner
            app_folder = await self.get_app_folder(file_name_base)
            self.config.test_runner_args.binary_path = str(app_folder / "Cynteract.exe")
            self.config.test_runner_args.test_id = file_name_base
            await main(self.config.test_runner_args)

            # upload screenshots
            passed, build_url = await self.upload_screenshots(file_name_base)
            if passed:
                return TestResult(
                    passed=True, details="All tests passed", target_url=build_url
                )
            else:
                return TestResult(
                    passed=False,
                    details="Some visual tests failed",
                    target_url=build_url,
                )
        except Exception as e:
            return TestResult(passed=False, details=str(e)[:140], target_url=None)

    async def get_app_folder(self, version: str) -> Path:
        app_folder = (
            Path.home()
            / "Documents"
            / "visual_testing"
            / "builds"
            / f"Cynteract-{version}"
        )
        if not app_folder.exists():
            zip_path = app_folder.with_name(app_folder.name + ".zip")
            if not zip_path.exists():
                # download the build zip from Google Cloud Storage
                base_url = "https://storage.googleapis.com/cynteract-unity-auto-build"
                download_url = f"{base_url}/windows/{zip_path.name}"
                print(f"Downloading build from {download_url}...")
                zip_path.parent.mkdir(parents=True, exist_ok=True)
                response = requests.get(download_url, stream=True)
                response.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        f.write(chunk)
            # extract the zip
            print(f"Extracting build to {app_folder}/...")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(app_folder)
        return app_folder

    async def process_commit(self, commit_sha: str):
        commit = self.repo.get_commit(commit_sha)
        commit_status = None
        for status in commit.get_statuses():
            if status.context == "visual regression test":
                commit_status = status
                break
        if commit_status is None or True:
            commit_status = commit.create_status(
                state="pending",
                context="visual regression test",
                description="Robot tests are running...",
                target_url="",
            )
            file_name_base = await self.get_file_name_base(commit)
            test_result = await self.run_commit_test(file_name_base)
            print(
                f"Test result for commit {commit.sha}: {'PASSED' if test_result.passed else 'FAILED'} - {test_result.details}"
            )
            commit_status = commit.create_status(
                state="success" if test_result.passed else "failure",
                context="visual regression test",
                description=test_result.details,
                target_url=test_result.target_url if test_result.target_url else "",
            )

    async def run(self):
        # poll action runs
        actions = self.repo.get_workflows()
        dev_build = None
        pr_build = None
        for action in actions:
            if action.name == ".github/workflows/on-development-push.yaml":
                dev_build = action
            elif action.name == ".github/workflows/on-pr-commit.yaml":
                pr_build = action
        assert dev_build is not None, "Development build workflow not found"
        assert pr_build is not None, "PR build workflow not found"

        # don't consider runs older than 7 days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=7)

        while True:
            # API docs: https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository
            dev_build_runs = dev_build.get_runs(
                status="success", created=f">{cutoff_date.strftime('%Y-%m-%d')}"
            )
            pr_build_runs = pr_build.get_runs(
                status="success", created=f">{cutoff_date.strftime('%Y-%m-%d')}"
            )

            cutoff_date = datetime.now(timezone.utc) - timedelta(minutes=5)

            for run in dev_build_runs:
                await self.process_commit(run.head_sha)
                return
            for run in pr_build_runs:
                await self.process_commit(run.head_sha)

            # wait 5 minutes before polling again
            await asyncio.sleep(300)
