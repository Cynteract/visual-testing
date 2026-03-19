import asyncio
import base64
import enum
import logging
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import github
import requests
from github.Commit import Commit
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from visual_regression_tracker import (
    Client,
    ClientConfig,
    Config,
    TestRun,
    VisualRegressionTracker,
    types,
)

from robot.__main__ import RobotArguments, async_main
from robot.config import get_data_dir, get_screenshot_dir


@dataclass
class GithubServiceConfig:
    github_pat: str
    robot_args: RobotArguments
    single_run_commit: str | None = None
    vrt_api_url: str | None = None
    vrt_api_key: str | None = None
    vrt_frontend_url: str | None = None
    vrt_email: str | None = None
    vrt_password: str | None = None


@dataclass
class VRTTestResult:
    ok_count: int
    unresolved_count: int
    new_count: int
    build_url: str | None


class CommitTestStatus(str, enum.Enum):
    ROBOT_PENDING = "robot_pending"
    ROBOT_RUNNING = "robot_running"
    ROBOT_FAILURE = "robot_failure"
    ROBOT_SKIPPED = "robot_skipped"
    VRT_PENDING = "vrt_pending"
    VRT_FAILURE = "vrt_failure"
    SUCCESS = "success"
    ERROR = "error"


def format_commit_status_description(status: CommitTestStatus, details: str) -> str:
    message = f"[{status.value}] {details}"
    if len(message) > 140:
        message = message[:137] + "..."
    return message


class TestResult:
    def __init__(
        self,
        test_status: CommitTestStatus,
        details: str,
        target_url: str | None = None,
    ):
        self.test_status = test_status
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
        if (
            config.vrt_api_url
            and config.vrt_api_key
            and config.vrt_email
            and config.vrt_password
        ):
            logging.info("Initialize VRT client.")
            self.vrt_client = Client(
                ClientConfig(
                    apiUrl=config.vrt_api_url,
                    email=config.vrt_email,
                    password=config.vrt_password,
                )
            )
            project = self.vrt_client.get_projects()[0]
            if project.name == "Default project":
                logging.info("Configure VRT project.")
                project.name = "Cynteract app"
                project.mainBranchName = "development"
                self.vrt_client.update_project(project)
            self.vrt_client.set_project(project.id)
        else:
            logging.warning(f"VRT client not initialized:")
            if not config.vrt_api_url:
                logging.warning("- VRT API URL not provided")
            if not config.vrt_api_key:
                logging.warning("- VRT API Key not provided")
            if not config.vrt_email:
                logging.warning("- VRT Email not provided")
            if not config.vrt_password:
                logging.warning("- VRT Password not provided")

    async def execute_command(self, *args: str, **kwargs) -> str:
        logging.info(f"Execute command: {' '.join(args)}")
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

    async def upload_screenshots(self, version: str, branch: str) -> VRTTestResult:
        build_result = VRTTestResult(0, 0, 0, None)
        if self.config.vrt_api_url and self.config.vrt_api_key:
            config = Config(
                apiUrl=self.config.vrt_api_url,
                apiKey=self.config.vrt_api_key,
                branchName=branch,
                project="Cynteract app",
                ciBuildId=version,
                # don't raise exception on NEW or UNRESOLVED images
                enableSoftAssert=True,
            )
            with VisualRegressionTracker(config) as vrt:
                build_result.build_url = f"{self.config.vrt_frontend_url}/{vrt.projectId}?buildId={vrt.buildId}"
                screenshot_dir = get_screenshot_dir(version)
                for image_path in screenshot_dir.glob("*.png"):
                    with image_path.open("rb") as f:
                        image_data = f.read()
                        imagebase64 = base64.b64encode(image_data).decode("utf-8")
                        result = vrt.track(
                            TestRun(
                                name=image_path.stem,
                                imageBase64=imagebase64,
                                diffTollerancePercent=0.2,
                            )
                        )
                        match result.testRunResponse.status:
                            case types.TestRunStatus.OK:
                                build_result.ok_count += 1
                            case types.TestRunStatus.UNRESOLVED:
                                build_result.unresolved_count += 1
                            case types.TestRunStatus.NEW:
                                build_result.new_count += 1
                    # yield
                    await asyncio.sleep(0)
        return build_result

    async def get_version_and_branch(self, commit: Commit) -> tuple[str, str]:
        branch = None
        development_branch = self.repo.get_branch("development")
        if development_branch.commit.sha == commit.sha or any(
            c.sha == commit.sha for c in development_branch.commit.parents
        ):
            version_info = await self.get_version_info(
                "--ci-development", "--commitish=" + commit.sha
            )
            branch = "development"
        elif commit.get_pulls().totalCount > 0:
            pr = commit.get_pulls().get_page(0)[0]
            version_info = await self.get_version_info(
                f"--ci-pr={pr.number}", "--commitish=" + commit.sha
            )
            branch = pr.head.ref
        else:
            raise RuntimeError(f"Neither development nor PR commit: {commit.sha}")
        _, file_name_base, _ = version_info.split(",")
        return file_name_base, branch

    async def download_file(self, url: str, file_path: Path) -> None:
        """Download a file with retry logic on connection errors."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        session = requests.Session()
        adapter = HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
            )
        )
        session.mount("https://", adapter)
        try:
            response = session.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=32768):
                    if chunk:
                        f.write(chunk)
        except Exception as e:
            file_path.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to download from {url}: {e}") from e

    async def run_commit_test(self, version: str, branch: str) -> TestResult:
        try:
            # run robot
            app_folder = await self.get_app_folder(version)
            self.config.robot_args.binary_path = str(app_folder / "Cynteract.exe")
            self.config.robot_args.test_id = version
            await async_main(self.config.robot_args)

            # upload screenshots
            vrt_result = await self.upload_screenshots(version, branch)
            if vrt_result.unresolved_count == 0 and vrt_result.new_count == 0:
                return TestResult(
                    test_status=CommitTestStatus.SUCCESS,
                    details="All tests passed",
                    target_url=vrt_result.build_url,
                )
            else:
                return TestResult(
                    test_status=CommitTestStatus.VRT_PENDING,
                    details=f"{vrt_result.unresolved_count} unresolved, {vrt_result.new_count} new images",
                    target_url=vrt_result.build_url,
                )
        except Exception as e:
            return TestResult(
                test_status=CommitTestStatus.ROBOT_FAILURE,
                details=str(e),
                target_url=None,
            )

    async def get_app_folder(self, version: str) -> Path:
        app_folder = get_data_dir(version) / f"Cynteract-{version}"
        if not app_folder.exists():
            zip_path = app_folder.with_name(app_folder.name + ".zip")
            if not zip_path.exists():
                logging.info(f"Download build for version {version}.")
                base_url = "https://storage.googleapis.com/cynteract-unity-auto-build"
                download_url = f"{base_url}/windows/{zip_path.name}"
                await self.download_file(download_url, zip_path)
            logging.info(f"Extract build to {app_folder}/ .")
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(app_folder)
        return app_folder

    async def process_commit(
        self, commit_sha: str, force_run: bool = False
    ) -> CommitTestStatus:
        """
        Check status of commit. Execute robot if not already done. Check for the result of the visual regression test.
        Returns True if processing is complete, False otherwise.
        """
        logging.info(f"Process commit {commit_sha}.")
        commit = self.repo.get_commit(commit_sha)
        version, branch = await self.get_version_and_branch(commit)

        # get commit status
        commit_status = None
        for status in commit.get_statuses():
            if status.context == "visual regression test":
                commit_status = status
                break

        commit_test_status = None
        if commit_status is None:
            commit_test_status = CommitTestStatus.ROBOT_PENDING
        else:
            commit_test_status = CommitTestStatus.ERROR
            for status in CommitTestStatus:
                if status.value in commit_status.description:
                    commit_test_status = status
                    break

        if commit_test_status is CommitTestStatus.ROBOT_PENDING or force_run:
            # start robot
            commit_status = commit.create_status(
                state="pending",
                context="visual regression test",
                description=format_commit_status_description(
                    CommitTestStatus.ROBOT_RUNNING, "Robot tests are running..."
                ),
                target_url="",
            )
            test_result = await self.run_commit_test(version, branch)
            logging.info(
                f"Test result for commit {commit.sha}: {test_result.test_status.value} - {test_result.details}"
            )
            commit_status = commit.create_status(
                state=(
                    "success"
                    if test_result.test_status == CommitTestStatus.SUCCESS
                    else "failure"
                ),
                context="visual regression test",
                description=format_commit_status_description(
                    test_result.test_status, test_result.details
                ),
                target_url=test_result.target_url if test_result.target_url else "",
            )
            return test_result.test_status
        elif commit_test_status is CommitTestStatus.VRT_PENDING:
            assert commit_status is not None
            # check if human review is done
            build = self.vrt_client.get_build(ciBuildId=version)
            if build.status == "passed":
                # all done
                commit_status = commit.create_status(
                    state="success",
                    context="visual regression test",
                    description=format_commit_status_description(
                        CommitTestStatus.SUCCESS, "All tests passed"
                    ),
                    target_url=commit_status.target_url,
                )
                return CommitTestStatus.SUCCESS
            elif build.status == "unresolved" or build.status == "new":
                # still pending
                return CommitTestStatus.VRT_PENDING
            elif build.status == "failed":
                # failed
                commit_status = commit.create_status(
                    state="failure",
                    context="visual regression test",
                    description=format_commit_status_description(
                        CommitTestStatus.VRT_FAILURE, "Visual regression tests failed"
                    ),
                    target_url=commit_status.target_url,
                )
                return CommitTestStatus.VRT_FAILURE
            else:
                logging.error(
                    f"Unknown VRT build status '{build.status}' for commit {commit.sha}"
                )
                return CommitTestStatus.ERROR
        elif (
            commit_test_status is CommitTestStatus.ROBOT_FAILURE
            or commit_test_status is CommitTestStatus.ROBOT_SKIPPED
            or commit_test_status is CommitTestStatus.SUCCESS
            or commit_test_status is CommitTestStatus.VRT_FAILURE
            or commit_test_status is CommitTestStatus.ERROR
        ):
            assert commit_status is not None
            logging.info(
                f"Robot already finished for commit {commit.sha} with status {commit_status.description}."
            )
            return commit_test_status
        else:
            logging.error(
                f'No action defined for commit {commit.sha} with status "{commit_test_status}"'
            )
            return commit_test_status

    async def run(self):
        # poll action runs
        logging.info("Fetch GitHub workflows.")
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
            logging.info("Retrieve recent workflow runs.")
            dev_build_runs = dev_build.get_runs(
                status="success",
                head_sha=self.repo.get_branch("development").commit.sha,
                created=f">{cutoff_date.strftime('%Y-%m-%d')}",
            )
            pr_build_runs = pr_build.get_runs(
                status="success",
                created=f">{cutoff_date.strftime('%Y-%m-%d')}",
            )

            # don't consider older runs if their visual tests (robot + human) are complete
            cutoff_date = datetime.now(timezone.utc) - timedelta(minutes=5)

            # don't consider runs for merged PRs or for non-head commits of open PRs
            current_pr_build_runs = []
            for run in pr_build_runs:
                for pr in run.pull_requests:
                    if pr.merged or pr.head.sha != run.head_sha:
                        continue
                    current_pr_build_runs.append(run)

            for run in list(dev_build_runs) + list(current_pr_build_runs):
                test_status = await self.process_commit(run.head_sha)
                # keep polling if human visual tests are still pending
                if test_status != CommitTestStatus.VRT_PENDING:
                    cutoff_date = min(cutoff_date, run.created_at)

            # wait 5 minutes before polling again
            await asyncio.sleep(300)
